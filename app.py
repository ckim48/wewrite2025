from flask import Flask, render_template, request,jsonify, url_for, flash, redirect, session

app = Flask(__name__)
app.secret_key = "randommessage"


@app.route('/', methods=['GET']) # / => main homepage; decorator
def index():
	return render_template('index.html')

@app.route('/read', methods=['GET']) # / => main homepage; decorator
def read():
	return render_template('read.html')

@app.route('/genre_management', methods=['GET']) # / => main homepage; decorator
def genre_management():
	return render_template('genre_management.html')

@app.route('/inprogress', methods=['GET']) # / => main homepage; decorator
def inprogress():
	return render_template('inprogress.html',user_role='admin')


@app.route('/detail', methods=['GET']) # / => main homepage; decorator
def detail():
	return render_template('detail.html',user_role='admin')


@app.route('/login', methods=['GET']) # / => main homepage; decorator
def login():
	return render_template('login.html')

@app.route('/register', methods=['GET']) # / => main homepage; decorator
def register():
	return render_template('signup.html')

@app.route('/write', methods=['GET'])
def write():
	return render_template('write.html')

@app.route('/collaborate', methods=['GET'])
def collaborate():
	return render_template('collaborate.html')

@app.route('/main', methods=['GET'])
def main():
	return render_template('main.html')

if __name__ == '__main__':
	app.run(debug=True)