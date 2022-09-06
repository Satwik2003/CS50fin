import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = db.execute("SELECT symbol, quantity, price, quantity*price AS total FROM portfolio WHERE id = ?", session['user_id'])
    user = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])

    if db.execute("SELECT symbol FROM portfolio WHERE id = ?", session['user_id']):
        tot = stocks[0]['total']
        c = user[0]['cash']

        total = usd(tot)
        cash = usd(c)
        bal = usd(tot+c)

        return render_template("index.html", stocks=stocks, cash=cash, bal=bal)
    else:
        return render_template("index.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'POST':
        if not request.form.get('symbol'):
            return apology("Enter a Valid Symbol")
        elif not request.form.get('shares'):
            return apology("Enter Quantity")
        elif int(request.form.get('shares')) < 1:
            return apology("Quantity can only be Positive")
        else:
            share = lookup(request.form.get('symbol'))

            if share == None:
                return apology("Please Enter a Valid Symbol")
            else:
                symbol = request.form.get('symbol')
                quantity = int(request.form.get('shares'))

                price = usd(quantity*share['price'])

                balance = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])
                #stock = db.execute("SELECT quantity FROM portfolio WHERE id = ? AND symbol = ?", session['user_id'], request.form.get('symbol'))

                if quantity*share['price'] > balance[0]['cash']:
                    return apology("Insufficient Balance")
                else:
                    db.execute("INSERT INTO purchase (id, symbol, quantity, price) VALUES (?, ?, ?, ?)", session['user_id'], symbol, quantity, quantity*share['price'])
                    time = db.execute('SELECT CURRENT_TIMESTAMP')
                    if not db.execute("SELECT * FROM portfolio WHERE id = ? AND symbol = ?", session['user_id'], symbol):
                        db.execute("INSERT INTO portfolio (id, symbol, quantity, price) VALUES (?, ?, ?, ?)", session['user_id'], symbol, quantity, quantity*share['price'])
                        db.execute("INSERT INTO history (id, symbol, quantity, action, price, date)VALUES (?, ?, ?, ?, ?, ?)", session['user_id'], symbol, quantity, 'buy', share['price'], time[0]['CURRENT_TIMESTAMP'])
                    else:
                        amount = db.execute("SELECT quantity FROM portfolio WHERE id = ? AND symbol = ?", session['user_id'], symbol)
                        db.execute("UPDATE portfolio SET quantity = ? WHERE id = ? AND symbol = ?", int(amount[0]['quantity'])+quantity, session['user_id'], symbol)
                        db.execute("INSERT INTO history (id, symbol, quantity, action, price, date)VALUES (?, ?, ?, ?, ?, ?)", session['user_id'], symbol, quantity, 'buy', share['price'], time[0]['CURRENT_TIMESTAMP'])

                    db.execute("UPDATE users SET cash = ?", (balance[0]['cash'])-(quantity*share['price']))


                    return redirect('/')


    else:
        return render_template('buy.html')



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transaction = db.execute("SELECT symbol, quantity, price, action, date FROM history WHERE id = ? ORDER BY date DESC", session['user_id'])

    return render_template("history.html", transaction=transaction)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == 'POST':
        if not request.form.get('symbol'):
            return apology("Please Enter Symbol")
        else:
            quote = lookup(request.form.get('symbol'))

            if quote == None:
                return apology("Please Enter a Valid Symbol")
            else:
                price = usd(quote['price'])
                return render_template('quoted.html', quote=quote, price=price)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get('username'):
            return apology("Must Provide a Username")
        elif not request.form.get('password'):
            return apology("Must Provide a Password")
        elif not request.form.get('confirmation'):
            return apology("Must Provide a Confirmation")
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            confirmation = request.form.get('confirmation')

            if password == confirmation:
                passhash = generate_password_hash(password)
                db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, passhash)
                return render_template("login.html")
            else:
                return apology("Password and Confirmation don't match")



    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == 'POST':
        if not request.form.get('symbol'):
            return apology("Must Enter Symbol")
        elif not request.form.get('shares'):
            return apology("Enter Quantity")
        elif int(request.form.get('shares')) < 1:
            return apology("Quantity can only be Positive")

        else:
            share = lookup(request.form.get('symbol'))
            symbol = request.form.get('symbol')

            stock = db.execute("SELECT quantity FROM portfolio WHERE id = ? AND symbol = ?", session['user_id'], request.form.get('symbol'))

            if share == None:
                return apology("Please Enter a Valid Symbol")
            elif not db.execute("SELECT * FROM portfolio WHERE id = ? AND symbol = ?", session['user_id'], symbol):
                return apology("You Don't Own The Stock")
            elif int(request.form.get('shares')) > stock[0]['quantity']:
                return apology("Insufficient stocks")
            else:

                quantity = int(request.form.get('shares'))
                cost = quantity*share['price']
                balance = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])
                time = db.execute('SELECT CURRENT_TIMESTAMP')


                db.execute("UPDATE portfolio SET quantity = ? WHERE id = ? AND symbol = ?", int(stock[0]['quantity'])-quantity, session['user_id'], symbol)
                db.execute('UPDATE users SET cash = ? WHERE id = ?',cost+int(balance[0]['cash']), session['user_id'])
                db.execute("INSERT INTO history (id, symbol, quantity, action, price, date)VALUES (?, ?, ?, ?, ?, ?)", session['user_id'], symbol, quantity, 'sell', share['price'], time[0]['CURRENT_TIMESTAMP'])

                return redirect('/')


    else:
        return render_template('sell.html')

@app.route("/addcash", methods=['GET','POST'])
@login_required
def addcash():
    if request.method == 'POST':
        amount = int(request.form.get('cash'))

        if not amount:
            return apology("Enter a Valid Amount")
        elif amount <= 0:
            return apology("Amount should be Positive")
        else:
            cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]['cash']+amount, session['user_id'])

            return redirect('/')
    else:
        return render_template("addcash.html")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
