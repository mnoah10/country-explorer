from flask import Flask, jsonify, request
import requests
app = Flask(__name__, static_folder="static", static_url_path="")

@app.route("/")
def index():
        return app.send_static_file("index.html")

if __name__=="__main__":
        app.run(port=8000, debug=True)