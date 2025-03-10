from flask import Flask, render_template, send_file, abort, request, redirect, Response, url_for, session

def setup_routing(app):
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', error=error), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('error.html', error=error), 500
