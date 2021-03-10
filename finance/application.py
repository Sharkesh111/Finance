import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
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

    user = session["user_id"]
    stocks = db.execute("SELECT symbol, shares FROM portfolios WHERE user_id = :user", user=user)

    if not stocks:
        return apology("You do not have any stocks")

    total = 0

    for stock in stocks:
        
        symbol = lookup(stock["symbol"])
        shares = stock["shares"]
        name = lookup(stock["symbol"])["name"]
        price = lookup(stock["symbol"])["name"]

        stock.update({ "name": name })

        price = symbol["price"]

        stock.update({ "price": usd(price) })

        value = price * shares

        stock.update({ "value": usd(value) })

        total = total + value

    cash = db.execute("SELECT cash FROM users WHERE id = :user", user = user)[0]["cash"]

    grand_total = total + cash

    return render_template("index.html", stocks = stocks, balance = usd(cash), value = usd(grand_total))




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("You must enter a ticker symbol")

        tickerSymbol = request.form.get("symbol").upper()
        stock = lookup(tickerSymbol)

        if stock == None:
            return apology("Must enter a valid ticker symbol")

        if not request.form.get("shares"):
            return apology("You must enter a quantity of shares you would like to buy")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Must enter a positive integer")

        if shares <= 0:
            return apology("Must enter a positive integer")

        cash = int(db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session["user_id"])[0]["cash"])
        price = shares * stock["price"]

        if price > cash:
            return apology("You do not have enough money to perform this transaction")

        total = cash - price

        stock=request.form.get("symbol")
        user=session["user_id"]

        db.execute("UPDATE users SET cash = :total WHERE id = :user", user=user, total=total)


        db.execute("INSERT INTO history (user_id, type, symbol, shares, price) VALUES (:user_id, :transaction_type, :symbol, :shares, :price)",
            user_id = user,
            transaction_type = "purchase",
            symbol = stock,
            shares = shares,
            price = format(price, '.2f'))

        portfolio = db.execute("SELECT shares FROM portfolios WHERE user_id = :user_id AND symbol = :symbol", user_id = user, symbol = stock)

        if len(portfolio) == 1:

            shares = portfolio[0]["shares"] + shares

            db.execute("UPDATE portfolios SET shares = :shares WHERE user_id = :user_id AND symbol = :symbol", user_id=user, symbol=stock, shares=shares)

        else:
            db.execute("INSERT INTO portfolios (user_id, symbol, shares) VALUES (:user_id, :symbol, :shares)", user_id=user, symbol=stock, shares=shares)

        return redirect("/")

    else:
        return render_template("buy.html")

    return apology("TODO")


@app.route("/history")
@login_required
def history():
    
    historys = db.execute("SELECT time, type, symbol, shares, price FROM history WHERE user_id = :user ORDER BY time DESC", user=session["user_id"])

    return render_template("history.html", historys = historys)



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
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

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
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("You must enter a ticker symbol")

        tickerSymbol = request.form.get("symbol").upper()
        stock = lookup(tickerSymbol)

        if stock == None:
            return apology("Must enter a valid ticker symbol")

        return render_template("quoted.html", stock=stock)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)

        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif not request.form.get("confirmation"):
            return apology("must provide confirmation password", 403)

        if request.form.get("password") != request.form.get("confirmation"):
            return apology("The password and confirmation password are not the same", 403)

        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))
        user = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)

        if user is None:
            return apology("Sorry, the username already exists", 403)

        session["user_id"] = user
        return redirect("/")


    else:
        return render_template("register.html")

    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("You must enter a ticker symbol")

        tickerSymbol = request.form.get("symbol").upper()
        ticker = lookup(tickerSymbol)

        if ticker == None:
            return apology("Must enter a valid ticker symbol")

        if not request.form.get("shares"):
            return apology("You must enter a quantity of shares you would like to buy")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Must enter a positive integer")

        if shares <= 0:
            return apology("Must enter a positive integer")

        symbol = request.form.get("symbol")

        user = session["user_id"]

        stocks = db.execute("SELECT shares FROM portfolios WHERE user_id = :user AND symbol = :symbol", user=user, symbol=symbol)

        if len(stocks) != 1:
            return apology("You do not have any shares for this stock")

        if stocks[0]["shares"] < shares:
            return apology("You are trying to sell more shares of a stock than total stock you have")

        price = lookup(symbol)["price"] * shares

        db.execute("INSERT INTO history (user_id, type, symbol, shares, price) VALUES (:user, :transaction_type, :symbol, :shares, :price)",
            user = user,
            transaction_type = "sell",
            symbol = symbol,
            shares = shares,
            price = format(price,".2f"))

        cash = db.execute("SELECT cash FROM users WHERE id = :user", user=user)[0]["cash"]

        cash = cash + price

        db.execute("UPDATE users SET cash = :cash WHERE id = :user", user=user, cash=cash)

        numOfShares = stocks[0]["shares"] - shares

        db.execute("UPDATE portfolios SET shares = :shares WHERE user_id = :user AND symbol = :symbol", user=user, symbol=symbol, shares=numOfShares)

        return redirect("/")

    else:
        stocks = db.execute("SELECT symbol FROM portfolios WHERE user_id =:user", user=session["user_id"])

        return render_template("sell.html", stocks = stocks)
        
@app.route("/add", methods=["GET", "POST"])
@login_required
def add():

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        if not request.form.get("deposit"):
            return apology("You must enter how much money you would like to deposit")
            
        deposit = request.form.get("deposit")
            
        try:
            num = int(deposit)
        except:
            return apology("Must enter a positive integer")

        if num <= 0:
            return apology("Must enter a positive integer")


        db.execute("UPDATE users SET cash = cash + :deposit WHERE id = :user", user = session["user_id"], deposit = deposit)

       
        return redirect("/")

    else:
        return render_template("add.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
    
