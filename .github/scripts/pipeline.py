"""Plans each pipeline stage and reports what runs where."""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

SERVICE = "tpp-global-payments"
ECR_REPO = "tpp-global-payments"
PREFIX = "global-payments"
ENVS = {
    "dev": ("GW", "us-east-2", "tpp-dev-ecs-cluster"),
    "qa": ("GW", "us-east-2", "tpp-qa-ecs-cluster"),
    "sandbox": ("GW", "us-east-2", "tpp-sandbox-ecs-cluster"),
    "prod": ("PROD", "us-east-1", "tpp-prod-ecs-cluster"),
}
VERSION = re.compile(rf"{PREFIX}-(qa|sandbox|prod)-1\.0\.0\.(\d+)")
SOURCE = re.compile(rf"{PREFIX}-(?:dev|qa)-(.+)-([0-9a-f]{{7}})")
ROLLED = re.compile(rf"{PREFIX}-(qa|sandbox|prod)-rolledback-1\.0\.0\.(\d+)")
FAILED = re.compile(rf"{PREFIX}-(qa|sandbox|prod)-failed-1\.0\.0\.(\d+)")


def fail(msg):
    sys.exit("::error::" + msg)


def aws(creds, region, *args):
    env = dict(os.environ, AWS_DEFAULT_REGION=region,
               AWS_ACCESS_KEY_ID=os.environ[creds + "_KEY"],
               AWS_SECRET_ACCESS_KEY=os.environ[creds + "_SECRET"],
               AWS_SESSION_TOKEN=os.environ[creds + "_TOKEN"])
    out = subprocess.run(["aws", *args, "--region", region, "--output", "json"], env=env, capture_output=True, text=True)
    if out.returncode:
        fail("aws %s: %s" % (" ".join(args[:2]), out.stderr.strip()))
    return json.loads(out.stdout)


def gh(path):
    req = urllib.request.Request("https://api.github.com/repos/%s/%s" % (os.environ["GITHUB_REPOSITORY"], path),
                                 headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                                          "Accept": "application/vnd.github+json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        if e.code in (404, 422):
            return None
        raise


def images():
    ids = aws("PROD", "us-east-1", "ecr", "list-images", "--repository-name", ECR_REPO,
              "--filter", "tagStatus=TAGGED")["imageIds"]
    return {i["imageTag"]: i["imageDigest"] for i in ids}


def running(env):
    creds, region, cluster = ENVS[env]
    svc = aws(creds, region, "ecs", "describe-services", "--cluster", cluster, "--services", SERVICE)["services"][0]
    settled = len(svc["deployments"]) == 1 and svc["deployments"][0]["rolloutState"] == "COMPLETED"
    container = svc["loadBalancers"][0]["containerName"]
    td = aws(creds, region, "ecs", "describe-task-definition", "--task-definition", svc["taskDefinition"])
    image = next(c["image"] for c in td["taskDefinition"]["containerDefinitions"] if c["name"] == container)
    return image.rsplit(":", 1)[1], settled, svc["deployments"][0]["createdAt"]


def settled_tag(env):
    tag, settled, since = running(env)
    if not settled:
        fail("%s has a rollout in progress; wait for it to finish" % env)
    return tag, since


def source_of(digest, tags):
    """(branch, sha7) of the build behind an image, read from its dev or QA branch tag."""
    found = [(m[1].replace("--", "/"), m[2], "-dev-" in t) for t, d in tags.items()
             if d == digest and (m := SOURCE.fullmatch(t))]
    # Identical builds share a digest; a release image is attributed to main or hotfix/ first.
    found.sort(key=lambda s: (s[0] != "main" and not s[0].startswith("hotfix/"), not s[2]))
    return found[0][:2] if found else None


def slug(branch):
    return re.sub(r"[^A-Za-z0-9_.-]", "-", branch.replace("/", "--"))


def compare(base, head):
    return gh("compare/%s...%s" % (base, head))


def contains(base, head):
    return (compare(base, head) or {}).get("status") in ("ahead", "identical")


def has_fix(prod_src, sha7):
    if contains(prod_src[1], sha7):
        return True
    # A squash or rebase merge gives the fix a new commit id, so also accept the merged hotfix PR.
    head = urllib.parse.quote("%s:%s" % (os.environ["GITHUB_REPOSITORY"].split("/")[0], prod_src[0]), safe="")
    prs = gh("pulls?state=closed&base=main&head=" + head) or []
    return any(pr["merged_at"] and contains(prod_src[1], pr["head"]["sha"]) and contains(pr["merge_commit_sha"], sha7)
               for pr in prs)


def prod_fix_check(tags, branch, sha7):
    prod_tag, _, _ = running("prod")
    prod_src = source_of(tags.get(prod_tag), tags) if prod_tag in tags else None
    if prod_src and not has_fix(prod_src, sha7):
        fail("Prod runs %s from %s at %s, which this release (%s at %s) does not contain. "
             "Merge %s into main first." % (prod_tag, prod_src[0], prod_src[1], branch, sha7, prod_src[0]))
    return prod_tag, prod_src


class Plan:
    def __init__(self):
        self.out, self.notes = {}, []

    def set(self, **kw):
        self.out.update({k: str(v) for k, v in kw.items()})

    def note(self, line):
        self.notes.append(line)
        print(line)

    def write(self, title):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.writelines("%s=%s\n" % kv for kv in self.out.items())
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("### %s\n\n" % title + "".join("- %s\n" % n for n in self.notes))


def older_active_run():
    wf = os.environ["GITHUB_WORKFLOW_REF"].split("@")[0].rsplit("/", 1)[1]
    me = int(os.environ["GITHUB_RUN_ID"])
    # Only older runs block, so two runs started together don't stop each other.
    for status in ("in_progress", "queued", "waiting", "pending", "requested"):
        for r in (gh("actions/workflows/%s/runs?status=%s&per_page=100" % (wf, status)) or {}).get("workflow_runs", []):
            if r["id"] < me:
                return r
    return None


def plan_dev(p, source):
    other = older_active_run()
    if other:
        fail("Another deploy is still running: %s (%s). Only one deploy runs at a time; "
             "wait for it to finish or reject it, then start again." % (other["display_title"], other["html_url"]))
    c = gh("commits/" + source)
    if not c:
        fail("branch %s not found" % source)
    sha = c["sha"]
    p.set(sha=sha, since=c["commit"]["committer"]["date"][:10], image_tag="%s-dev-%s-%s" % (PREFIX, slug(source), sha[:7]), extra_tags=PREFIX + "-dev-latest",
          labels="org.opencontainers.image.revision=%s,org.opencontainers.image.ref.name=%s" % (sha, source))
    p.note("Building %s at %s" % (source, sha[:7]))
    if source != "main" and not source.startswith("hotfix/"):
        msg = "%s is a feature branch: this run deploys to dev and QA only, then stops." % source
        p.note(msg)
        print("::notice::" + msg)


def plan_qa(p, branch, sha7):
    dev_tag = "%s-dev-%s-%s" % (PREFIX, slug(branch), sha7)
    tags = images()
    if dev_tag not in tags:
        fail("%s at %s has not been built in dev" % (branch, sha7))
    version = ""
    if branch == "main" or branch.startswith("hotfix/"):
        rolled = sorted("1.0.0.%s from %s" % (m[2], m[1]) for t, d in tags.items()
                        if d == tags[dev_tag] and (m := ROLLED.fullmatch(t)))
        if rolled:
            fail("%s at %s is %s, which was rolled back. Push a fix and start a new run." % (branch, sha7, rolled[0]))
        same = [int(v[2]) for t, d in tags.items() if d == tags[dev_tag] and (v := VERSION.fullmatch(t))]
        # Counts every environment, so numbers left by the older sandbox-minted scheme are never reused.
        n = max(same) if same else 1 + max([int(v[2]) for t in tags if (v := VERSION.fullmatch(t))], default=0)
        version = "1.0.0.%d" % n
        new = "%s-qa-%s" % (PREFIX, version)
        p.note("%s at %s: version %s%s" % (branch, sha7, version, " (this image already had it)" if same else ""))
    else:
        new = "%s-qa-%s-%s" % (PREFIX, slug(branch), sha7)
        p.note("Feature branch %s at %s: no version, the run ends after QA" % (branch, sha7))
    p.set(image_tag=new, promote_from=dev_tag, version=version)


def not_newer(env, version):
    tag, _ = settled_tag(env)
    v = VERSION.fullmatch(tag)
    if v and int(v[2]) > int(version.rsplit(".", 1)[1]):
        fail("%s already runs 1.0.0.%s, newer than %s. Use rollback to go back to an older version." % (env, v[2], version))


def plan_sandbox(p, version):
    qa_tag = "%s-qa-%s" % (PREFIX, version)
    tags = images()
    if qa_tag not in tags:
        fail("%s not found" % qa_tag)
    src = source_of(tags[qa_tag], tags)
    if not src:
        fail("cannot tell which commit %s was built from" % qa_tag)
    branch, sha7 = src
    prod_tag, prod_src = prod_fix_check(tags, branch, sha7)
    if prod_src:
        changes = [c["commit"]["message"].splitlines()[0] for c in compare(prod_src[1], sha7)["commits"]]
    else:
        changes = []
        p.note("Prod runs %s, which has no recorded commit: hotfix merge-back check skipped" % prod_tag)
    # After the hotfix check, so a release missing a hotfix is told to merge it, not to roll back.
    not_newer("sandbox", version)
    p.set(image_tag="%s-sandbox-%s" % (PREFIX, version), promote_from=qa_tag)
    p.note("Releasing version %s, built from %s at %s" % (version, branch, sha7))
    p.note("Prod runs %s; changes since then: %d" % (prod_tag, len(changes)))
    p.notes += ["  - %s" % c for c in changes[-20:]]


def plan_prod(p, version):
    sb_tag = "%s-sandbox-%s" % (PREFIX, version)
    tags = images()
    if sb_tag not in tags:
        fail("%s not found" % sb_tag)
    src = source_of(tags[sb_tag], tags)
    if not src:
        fail("cannot tell which commit %s was built from" % sb_tag)
    prod_fix_check(tags, *src)
    not_newer("prod", version)
    p.set(image_tag="%s-prod-%s" % (PREFIX, version), promote_from=sb_tag)
    p.note("Releasing version %s (%s at %s) to prod" % (version, *src))


def plan_rollback(p, env):
    tags = images()
    current, _ = settled_tag(env)
    v = VERSION.fullmatch(current)
    if not v or v[1] != env:
        fail("%s runs %s, not a released version, so there is no previous version to go back to" % (env, current))
    # Skips versions rolled back before or whose rollout here never finished, so rollback lands on one that ran.
    bad = {int(m[2]) for t in tags if (m := ROLLED.fullmatch(t) or FAILED.fullmatch(t)) and m[1] == env}
    older = sorted((int(m[2]) for t in tags if (m := VERSION.fullmatch(t)) and m[1] == env
                    and int(m[2]) < int(v[2]) and int(m[2]) not in bad), reverse=True)
    if not older:
        fail("%s runs 1.0.0.%s and no earlier version has run in %s" % (env, v[2], env))
    version = "1.0.0.%d" % older[0]
    want = "%s-%s-%s" % (PREFIX, env, version)
    p.set(rollback="true", image_tag=want, version=version, rolled_back="1.0.0." + v[2])
    p.note("Rolling %s back from 1.0.0.%s to %s%s" % (env, v[2], version, "; sandbox stays as it is" if env == "prod" else ""))
    p.note("No database check: this service has no migrations")


def mark_rolled_back(env, version):
    src = aws("PROD", "us-east-1", "ecr", "batch-get-image", "--repository-name", ECR_REPO,
              "--image-ids", "imageTag=%s-%s-%s" % (PREFIX, env, version))["images"][0]
    tag = "%s-%s-rolledback-%s" % (PREFIX, env, version)
    if images().get(tag) == src["imageId"]["imageDigest"]:
        return print("%s already marked" % tag)
    aws("PROD", "us-east-1", "ecr", "put-image", "--repository-name", ECR_REPO, "--image-tag", tag,
        "--image-manifest", src["imageManifest"], "--image-manifest-media-type", src["imageManifestMediaType"])
    print("Marked %s as rolled back (%s); later rollbacks skip it" % (version, tag))


def where():
    tags = images()
    rows = []
    for env in ENVS:
        tag, settled, since = running(env)
        own = SOURCE.fullmatch(tag)
        src = (own[1].replace("--", "/"), own[2]) if own else source_of(tags.get(tag), tags) if tag in tags else None
        v = VERSION.fullmatch(tag)
        rows.append("| %s | %s | %s | %s |%s" % (env, "1.0.0." + v[2] if v else "-",
                    "%s @ %s" % src if src else "unknown", since[:16].replace("T", " "),
                    "" if settled else " rolling out"))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
        fh.write("### What runs where\n\n| Env | Version | Branch @ commit | Deployed (UTC) |\n|---|---|---|---|\n")
        fh.write("\n".join(rows) + "\n")
    print("\n".join(rows))


def main():
    step = sys.argv[1]
    if step == "where":
        return where()
    source, version = os.environ.get("SOURCE", ""), os.environ.get("VERSION", "").strip()
    env = os.environ.get("ROLLBACK_ENV", "prod")
    if step == "mark":
        return mark_rolled_back(env, version)
    p = Plan()
    {"plan": lambda: plan_dev(p, source), "qa": lambda: plan_qa(p, source, os.environ["SHA"][:7]),
     "sandbox": lambda: plan_sandbox(p, version), "prod": lambda: plan_prod(p, version),
     "rollback": lambda: plan_rollback(p, env)}[step]()
    p.write("Plan: %s" % ("dev" if step == "plan" else "roll %s back to %s" % (env, p.out.get("version"))
                          if step == "rollback" else step))


if __name__ == "__main__":
    main()
