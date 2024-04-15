from sanic import Sanic

from service.blue_print import bp as bp_bp

app = Sanic("GlobalPaymentsService")

app.blueprint(bp_bp)
