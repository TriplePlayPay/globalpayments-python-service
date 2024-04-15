from service import app

if __name__ == '__main__':
    app.prepare(
        fast=True,
        motd=False,
        verbosity=0,
        access_log=False,
    )
    app.run(host="0.0.0.0")
