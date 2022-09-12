import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Assign variable to dict with portfolio data
    currentUser = session["user_id"]
    userPortfolioTableID = ("user_" + (str(currentUser)) + "_portfolio")
    cash = db.execute("SELECT cash FROM users WHERE id = ?", currentUser)
    cashValue = usd(cash[0]["cash"])
    grandTotal = cash[0]["cash"]

    try:
        portfolio = db.execute("SELECT * FROM ?", userPortfolioTableID)
        for stock in portfolio:
            currentMarketPrice = lookup(stock["stockSymbol"])
            price = currentMarketPrice["price"]
            total = price * stock["sharesOfStock"]
            stock.update({'price': usd(price), 'totalPrice': usd(total)})
            grandTotal += total
    except:
        portfolio = []


    return render_template("index.html", portfolio=portfolio, cash=cashValue, grandTotal=usd(grandTotal))



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # If form is submitted via POST
    if request.method == "POST":

        # Ensure user input for stock symbol is 1) not blank and 2) is a valid symbol
        symbolInput = request.form.get("symbol")
        lookupData = lookup(symbolInput)
        if not symbolInput:
            return apology("must provide symbol", 400)
        elif not lookupData:
            return apology("invalid symbol", 400)

        # Ensure the input for number of shares is 1) not blank and 2) is a valid number (a positive integer)
        sharesInput = request.form.get("shares")

        try:
            shares = int(sharesInput)
            isSharesInt = True
        except:
            isSharesInt = False

        if not sharesInput:
            return apology("must provide shares", 400)
        elif (not isSharesInt) or (shares <= 0):
           return apology("shares must be a positive integer", 400)

        # Stock symbol and number of shares are  valid
        # Assign data values to variables
        name = lookupData["name"]
        price = lookupData["price"]
        symbol = lookupData["symbol"]

        # Lookup currently logged in user to make sure they have enought money.
        requestedBuyAmount = price * shares
        currentUser = session["user_id"]
        userCashTable = db.execute("SELECT cash FROM users WHERE id = ?", currentUser)
        userCashAmount = userCashTable[0]["cash"]

        # Ensure the user has enough cash to complete purchase
        if requestedBuyAmount > userCashAmount:
            return apology("Can't afford", 400)

        # Proceed with transaction, first name user transaction and portfolio tables corresponding to their user ID
        userTransactionsTableID = ("user_" + (str(currentUser)) + "_transactions")
        userPortfolioTableID = ("user_" + (str(currentUser)) + "_portfolio")

        # Checks if user has existing transaction log, if not creates new transaction and portfolio log via SQL tables interacting with database
        try:
            db.execute("SELECT * FROM (?)", userTransactionsTableID)

        except:
            db.execute("CREATE TABLE ? (transactionID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, Date DATETIME NOT NULL, transactionType TEXT NOT NULL, stockSymbol TEXT NOT NULL, stockPrice NUMERIC NOT NULL, numShares NUMERIC NOT NULL, transactionAmount NUMERIC NOT NULL)", userTransactionsTableID)
            db.execute("CREATE TABLE ? (stockSymbol TEXT NOT NULL, stockName TEXT UNIQUE, sharesOfStock NUMERIC NOT NULL)", userPortfolioTableID)

        #then execute transaction, updating transaction logs by inserting data, and update the users cash amount to reflect the transaction
        db.execute("INSERT INTO ? (Date, transactionType, stockSymbol, stockPrice, numShares, transactionAmount) VALUES (?, 'buy', ?, ?, ?, ?)", userTransactionsTableID, datetime.datetime.now(), symbol, price, shares, requestedBuyAmount)
        db.execute("UPDATE users SET cash=? WHERE id=?", (userCashAmount - requestedBuyAmount), currentUser)

        # update users portfolio table based on transaction
        # first search if user already has existing shares of the stock
        currentPortfolio = db.execute("SELECT stockSymbol FROM ? WHERE stockSymbol=?", userPortfolioTableID, symbol)

        if not currentPortfolio:
            # create a new entry in users portfolio
            db.execute("INSERT INTO ? (stockSymbol, stockName, sharesOfStock) VALUES (?, ?, ?)", userPortfolioTableID, symbol, name, shares)
        else:
            # update the current portfolio
            db.execute("UPDATE ? SET sharesOfStock = sharesOfStock + ? WHERE stockSymbol = ?", userPortfolioTableID, shares, symbol)

        # redirect user to home page, to display user portfolio
        flash("Purchase Complete!")
        return redirect("/")

    # User reached route via GET (via clicking link or by redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Retrieve current user's information to access SQL transaction's table
    currentUser = session["user_id"]
    userTransactionsTableID = ("user_" + (str(currentUser)) + "_transactions")

    # First check user has previous transactions
    try:
        # Assign variable to list of dict objects with transaction history data
        history = db.execute("SELECT * FROM ?", userTransactionsTableID)
        return render_template("history.html", history=history)
    except:
        flash("No transactions in history!")
        return redirect("/")



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

    if request.method ==  "POST":

        # Ensure symbol was inputted and submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Retrieve the symbol and look up it's stock price
        else:
            symbolInput = request.form.get("symbol")
            lookupData = lookup(symbolInput)

            # Ensure the look up was successful and returned valid data, then return data to user
            if lookupData != None:
                return render_template("quoted.html", name=lookupData["name"], price=usd(lookupData["price"]), symbol=lookupData["symbol"])

            # Stock symbol inputted by user was invalid
            else:
                return apology("invalid symbol", 400)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        #Require that a user input a username.
        if not request.form.get("username"):
            return apology("must provide username", 400)

        #Check that the username is available and does not already exist
        else:
            attemptedUsername = request.form.get("username")
            usernames = db.execute("SELECT username FROM users") #note returns list of dictionaries
            for x in usernames: #for each dictionary
                if attemptedUsername in (x["username"]):
                    return apology("username already exists", 400)

        #Require that a user input a password and confirmation password
        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("must provide password and confirmation password", 400)

        #Require the passwords to match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        #Register the new user by adding it to the database
        attemptedPassword = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", attemptedUsername, attemptedPassword)

        # Log registered user in
        flash("Registration Complete! Now login")
        return render_template("login.html")


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # First retrieve current user's information
    currentUser = session["user_id"]
    userTransactionsTableID = ("user_" + (str(currentUser)) + "_transactions")
    userPortfolioTableID = ("user_" + (str(currentUser)) + "_portfolio")

    # First check user owns shares of stock
    try:
        db.execute("SELECT * FROM ?", userPortfolioTableID)
    except:
        flash("No stocks in portfolio to sell!")
        return redirect("/")

    # Then assign all stock symbols in users portfolio to variable (list of dict objects)
    userStockSymbols = db.execute("SELECT stockSymbol FROM ?", userPortfolioTableID)

    if request.method == "POST":

        # assign selected symbol to variable
        selectedSymbol = request.form.get("symbol")

        # check that user made a stock selection
        if not selectedSymbol:
            return apology("must select symbol", 400)

        # check that the users stock symbol selection is a valid symbol in their portfolio
        symbols =  []
        for stock in userStockSymbols:
            symbols.append(stock["stockSymbol"])
        if selectedSymbol not in symbols:
            return apology("invalid symbol selected", 400)


        # Ensure the input for number of shares is 1) not blank and 2) is a valid number (a positive integer)
        # and 3) the user has at least that many shares of the stock in their portfolio

        # 1st requirement validaion
        sharesInput = request.form.get("shares")
        numSharesAvailable = db.execute("SELECT sharesOfStock FROM ? WHERE stockSymbol=?", userPortfolioTableID, selectedSymbol)
        numSharesAvailable = numSharesAvailable[0]["sharesOfStock"]

        # 2nd requirement validation
        try:
            shares = int(sharesInput)
            isSharesInt = True
        except:
            isSharesInt = False

        # 3rd requirement validation
        if not sharesInput:
            return apology("must provide shares", 400)
        elif (not isSharesInt) or (shares <= 0):
            return apology("shares must be a positive integer", 400)
        elif shares > numSharesAvailable:
            return apology("too many shares", 400)


        # Complete the sell transaction at stock's current price

        # First lookup price and stock data
        lookupData = lookup(selectedSymbol)
        # name = lookupData["name"]
        price = lookupData["price"]
        symbol = lookupData["symbol"]

        # Calculate total transaction sell amount
        requestedSellAmount = price * shares

        # Complete transaction on users transaction table
        db.execute("INSERT INTO ? (Date, transactionType, stockSymbol, stockPrice, numShares, transactionAmount) VALUES (?, 'sell', ?, ?, ?, ?)", userTransactionsTableID, datetime.datetime.now(), symbol, price, shares, requestedSellAmount)

        # Update users cash amount and portfolio tables
        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", requestedSellAmount, currentUser)
        db.execute("UPDATE ? SET sharesOfStock = sharesOfStock - ? WHERE stockSymbol = ?", userPortfolioTableID, shares, symbol)

        # Remove the stock completely from the portfolio if 0 shares are left
        db.execute("DELETE FROM ? WHERE sharesOfStock = 0", userPortfolioTableID)

        # Redirect user to home page, to display user portfolio
        flash("Sold!")
        return redirect("/")


    # User reached route via GET (as by clicking a link or via redirect
    else:
        return render_template("sell.html", userStockSymbols=userStockSymbols)
