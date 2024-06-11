# Wifey Automation Tool
![forthebadge](https://forthebadge.com/images/badges/built-with-love.svg) ![forthebadge](https://forthebadge.com/images/badges/made-with-python.svg) ![forthebadge](https://forthebadge.com/images/badges/code-sucks-it-works.svg)

Automate execution of trades based on [Wifey Alpha](https://wifeyalpha.com/) allocation emails

# Requirements
- Windows (no clue what the minimum version is - I tested on Windows 10)
- An updated MetaTrader 5 client from your broker
- Python 3.11 or higher
- The latest MetaTrader5 Python package

# Installation
- Grab Python 3.11 or newer from https://www.python.org/downloads/ (using the Windows installer is fine and convenient)
  - You can also use different methods to install Python, but the following steps might need to be adjusted then
- Install python **as administrator** (This is important! The script won't work if you do not install as admin)
- Open an administrator command shell (Windows button + `cmd` + Ctrl + Shift + Enter) (This is important! The script won't work if you do not install as admin)
- Type `py --version` to see if you get a positive result, informing you about the installed python version
  - If you do not get a response like `Python 3.11.9`, your Python installation did not go right and you might need to try again
- Type `py -m pip install MetaTrader5 numpy` to install the python connector for MetaTrader 5, numpy and their dependencies
- Download trader.py from this repository and copy it to a folder of your choice
- Open trader.py in a text editor (e.g. notepad) and go through the first 60 lines or so, configuring your email access, strategy to trade, investment capital and define the symbols traded in the strategy

You are now set as far as installation and configuration of required packages goes.

# Running Wifey Automation Tool
The script will always connect to the last MetaTrader account that was used. If you use multiple MT5 accounts, make sure you connect to the one you want to use for Wifey Alpha before running Wifey Automation Tool.

**If you want to do a test run first, make sure you connect to a Demo/Paper account before running Wifey Automation Tool. It is highly recommended to do this for the first time, to make sure everything works as expected**

You can run the program manually, which is useful for testing the initial setup. Once everything is figured out and tested, you can use the Windows Task Scheduler to run it automatically.

## Manual execution
- Open a command shell (Windows button + `cmd` + Enter)
- Type `py C:\your\path\to\trade.py` and hit Enter

**Note for testing initial setups:**

The tool will check if an allocation email has been sent on the same day (based on UTC timezone) of when the script is ran. If there is no email yet (e.g. you test before 19:53 UTC), the tool will just wait for new emails to arrive and not trade. In order to be able to test, you might have to send yourself an email formatted like the Wifey Alpha emails and change the "sender" variable in trader.py to match your own email address. Otherwise the script will just sit there and wait for the next allocation emails to be sent at 19:53 UTC. After initial setup testing is complete, make sure to set the sender variable back to noreply@wifeyalpha.com again, so that it picks up the proper emails.

The allocation emails are sent in both formats in one email - raw text and HTML formatted. Your manual email client will usually show the HTML variant. Wifey Automation Tool uses the raw text variant for its trading. The two variants have a small difference: The raw text variant adds a colon after the symbol, the HTML variant does not. If you don't know how to find the raw text variant of one of the previous emails, you can use the following sample mail and send it to yourself as **unformatted, raw text email** (subject is identical to the first line of the email. The date mentioned in the email text is irrelevant as it is ignored by the tool):

    Daily Long/Short
    Last Computation Date: 2024-06-11
    Last Allocation Date: 2024-06-11
    SPY: 100.0%

You can change the 100% to any other value from -100.0% to 100.0%, send it to yourself and run Wifey Automation Tool again and it will adjust your positions to match the allocation. As stated previously - do this testing on a Demo/Paper account! Do not use a live account for testing like this. You might incur fees and potential trading losses!

## Automatic execution
- Open the Windows Task Scheduler (Windows button + `taskschd.msc` + Enter)
- On the right side, click "Create Basic Task"
- Pick any name and description you like
- Trigger is "weekly"
- Start day is whenever you want to start, e.g. today. Earliest start time is less than 5 minutes before Wifey Alpha emails get sent (I recommend to trigger at 19:51 UTC or whatever that time is in your computer's local timezone), latest 2 minutes before market closes
- Repeat once a week on all days except Saturday and Sunday
- Action is "Start a program"
- Program / Script is the path to your python executable (e.g. `C:\Python311\python.exe`)
- Add arguments is the path to your trade.py file (e.g. `C:\your\path\to\trade.py`)
- Start in is the folder where you want the log file to be created at. The log file is important to share with me if you need help with errors (e.g. same path like your trade.py - `C:\your\path\to\`)
- Make sure your computer is turned on when the script is scheduled to start! (You could set this up in a Windows virtual machine, e.g. on AWS or some other cloud hoster. Starting Windows 15 minutes prior to script execution and then shutting the VM down again on market close should not cost more than ~5 EUR / month)

You can now find your new scheduled task in the long list of other scheduled tasks. Sort the list by name and scroll to the name that you gave the task. You can double click on it to modify it after initial creation.

Here are screenshots of my configured scheduled task. My Windows is in German unfortunately, but the UI layout is the same. You can figure out which field is which on your system. If anyone wants to contribute English interface screenshots, be my guest :)

**Trigger tab:**

![image](https://github.com/SwimlanesOnline/WifeyAutomation/assets/226377/feaba88a-2d5f-4f3b-b3e3-65ad4a246e1f)
(End after 30 minutes is optional. The script will quit automatically on its own after 30 minutes)

**Actions tab:**

![image](https://github.com/SwimlanesOnline/WifeyAutomation/assets/226377/79e13049-de15-4795-afa3-7ba139787a89)


# Limitations
- The script will invest based on real value, including leverage. If your account runs 2x leverage and you define 10k to be invested, it won't go above 5k due to the leverage taking care of the remaining 5k
  - If your account defines different leverages for different symbols, make sure that your configured investment amount is low enough that the cash in your account is sufficient to buy your lowest leverage symbol at 100% allocation
- Use leverage at your own risk! You can lose all your money. I highly recommend not using leverage for programs that Wifey Alpha does not intend to be leveraged
- Google will close the email connection after about 5 minutes. Do not run the script too early. Usually WifeyAlpha sends allocation emails at 19:53 UTC and I start the script at 19:51 for instant trades as the emails arrive.
  - It is OK to run the script after the emails have been sent, it will still grab the allocations and trade correctly. You just need to run it early enough before the market closes and late enough to not run into the Google email timeout (if you don't use Google, you might have to experiment to see what your provider's timeout is)
- The script can not recognize trades that you make manually. The script will always match all positions for the symbols used in the strategy of your choice to the allocations sent via email. It will sell or buy as necessary to achieve email allocations
  - It is OK to trade manually or with other programs on symbols that are **not part** of the Wifey Alpha strategy that you want to automate
- The script can not pick a specific MetaTrader account. It will always connect to the last account that the MetaTrader 5 client was connected to
- The script does not support Meta Trader 4 or any other trading interface (IBKR is planned)
- Your email password will be visible in the python script unencrypted. Make sure nobody who is not authorized can gain access to your computer.

# ToDo
These are the features I want to work on next. No promises on timeline
- Encrypted password storage
- Improve IMAP IDLE / keep-alive to support checking emails for longer than 5 minutes
- IBKR API support
  - Encapsulate API from trading logic
- Show post rebalance allocations and send email if it doesn't match Wifey Alpha email allos

That's it. Now you know everything to run this Wifey Automation Tool. If you are a software engineer and read my terrible code, please be easy on me. Professionally I'm just a mere Product Manager, not a SE. If the code drives you crazy, fix it and send a merge request! :)
