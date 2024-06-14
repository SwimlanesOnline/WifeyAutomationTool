#!/usr/bin/env python3

###
# Execute Wifey Alpha strategies by pulling allocations
# from emails via IMAP and execute trades via MetaTrader 5.
# Program written by Sascha Jüngling <sjuengling@gmail.com>
###

# Make your edits in between the quotation marks "edit here" below (except for the investment amount, which has none).
# Do not remove the hash # signs in front of the lines.

# The URI of your email provider's IMAP server
imapServer = "imap.gmail.com" 

# Your email address
email = "example@gmail.com" 

# Your email's password (for GMail and some others you will need to create an app password and cannot use your regular password!)
# For GMail, you can set up an app password here: https://myaccount.google.com/apppasswords
emailPassword = "your password goes here" 

# Which Wifey strategy do you want to run? This is the strategy name exactly as written in Wifey's email subject line.
# Keep in mind that some strategies differ in name compared to the website (e.g. "Great White" in the Strategy Database is 
# "Long/Short Equity Daily Indicator" via emails)
strategy = "Daily Long/Short" 

# This is the sender email address, so it won't trigger on random other people's emails with the same subject line. This is not hardened
# for security - people can easily fake sender addresses. Don't tell anybody which email you use to receive your allocations.
# Usually it can stay unchanged.
sender = "noreply@wifeyalpha.com"

# How much money do you want to allocate to the strategy? This automation will trade the real value according to this line. 
# So if you use leverage, the money used in your account will be less than the amount mentioned here. E.g. if you
# define an investmentAmount of 10k and use 2x leverage, only 5k will be allocated. If allocations are below the minimum lot size regularly,
# account for your leverage by increasing your investment amount here. Drawdowns will then require additional margin.
# If you use leverage, you can get liquidated and lose all your money!
investmentAmount = 10000 

# Define here which ticker name from the Wifey Alpha strategy that you want to trade maps to which symbol on your broker.
# You don't need to define mappings for USD - it will simply be leftover uninvested in your account.
# Note: This program does not do currency conversion. If your account currency is not USD and the fx rate is far off 1:1, it'll get messy
# The pattern works like this (you need to define both sides, the Wifey Strategy's tickers as well as your broker's pendant)
# "wifey symbol": "your broker symbol",
symbolMap = {
    "SPY": "US500", 
}

# Example of running a strategy with multiple possible allocation symbols:
# symbolMap = {
#     "SPY": "US500", 
#     "BIL": "BIL.ETF", 
#     "IEF": "IEF.ETF", 
#     "GSG": "GSG.ETF", 
#     "VEA": "EFA.ETF", 
#     "GLD": "GLD.ETF", 
#     "AGG": "AGG.ETF",
# }

######################################
### No more change past this point ###
######################################

import threading, _thread, os, time, re, sys, signal, logging
from datetime import datetime
from imaplib import IMAP4_SSL
from collections import namedtuple
import MetaTrader5 as mt

logging.basicConfig(
    level=logging.INFO,
    filename="text.log",
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
# add the handler to the root logger
logging.getLogger('').addHandler(console)

def signal_handler(signum, frame):
    signal.signal(signum, signal.SIG_IGN) # ignore additional signals
    cleanQuit()
    
def cleanQuit(timedOut=False):
    if timedOut:
        logging.info("Exiting after timeout %s", timeout)
    else:
        logging.info("Received termination signal, cleaning up before exiting")
    mt.shutdown()
    logging.info("cleaned up, exiting")
    os._exit(0)

def receiveAllosIMAP(strategy, sender):
    with IMAP4_SSL(host=imapServer) as M: # "with" will automatically issue M.logout() at the end. timeout 14min
        M.login(email, emailPassword)
        M.select(readonly=True)
        typ, numMsgs = M.search(None, '(FROM "'+ sender +'")', '(SUBJECT "' + strategy + '")', '(SINCE "' + datetime.utcnow().strftime("%d-%b-%Y") + '")') # '(SINCE "25-Apr-2024")' # '(SINCE "' + datetime.utcnow().strftime("%d-%b-%Y") + '")'

        idling = False
        while True and len(numMsgs[0]) == 0:
            if idling is not True:
                M.send(b"%s IDLE\r\n"%(M._new_tag()))
                idling = True
            logging.info("Waiting for server to notify about new mail...")
            line = M.readline().strip()
            logging.info("readline ending")
            # M.send(b"%s DONE\r\n"%(M._new_tag()))
            if line.startswith(b'* BYE ') or (len(line) == 0):
                logging.error("IMAP server ended connection, leaving")
                break
            if line.endswith(b'EXISTS'):
                logging.info("new mail arrived")
                M.send(b"%s DONE\r\n"%(M._new_tag()))
                idling = False
                typ, numMsgs = M.search(None, '(FROM "'+ sender +'")', '(SUBJECT "' + strategy + '")', '(SINCE "' + datetime.utcnow().strftime("%d-%b-%Y") + '")') 
                if len(numMsgs[0]) == 0: 
                    logging.info("didn't find a mail satisfying the criteria")
                    M.send(b"%s IDLE\r\n"%(M._new_tag()))
                    idling = True
                    continue
                else: 
                    logging.info("found a mail")
                    break
        
        for num in numMsgs[0].split():
            typ, data = M.fetch(num, '(BODY[1])') # plain only, no HTML
            #print('Message %s\n%s\n' % (num, data[0][1]))
            
            if data == None: 
                logging.error("couldn't fetch mail")
                return None
            else: 
                logging.info("fetched mail")
            return re.findall(r"([A-Z]+)\:\s+(-?\d+\.\d+)\%", str(data[0][1])) # e.g.: \nSPY: 100.00%

def initMT():
    # establish connection to the MetaTrader 5 terminal
    if not mt.initialize():
        logging.error("initialize() failed, error code = %s",mt.last_error())
        os._exit(0)

def prepareRequest(symbol, lot, txType, positionID=0, filling=mt.ORDER_FILLING_FOK):
    # prepare the buy request structure
    symbol_info = mt.symbol_info(symbol)
    if symbol_info is None:
        logging.error("%s not found, can not call order_check()", symbol)
        mt.shutdown()
        os._exit(0)
    
    # if the symbol is unavailable in MarketWatch, add it
    if not symbol_info.visible:
        logging.info("%s is not visible, trying to switch on", symbol)
        if not mt.symbol_select(symbol,True):
            logging.error("symbol_select(%s) failed, exit", symbol)
            mt.shutdown()
            os._exit(0)
    
    if txType ==  "BUY":
        price = mt.symbol_info_tick(symbol).ask
        reqType = mt.ORDER_TYPE_BUY
    elif txType ==  "SELL":
        price = mt.symbol_info_tick(symbol).bid
        reqType = mt.ORDER_TYPE_SELL
    
    if filling & mt.ORDER_FILLING_FOK == mt.ORDER_FILLING_FOK:
        mode = mt.ORDER_FILLING_FOK
    elif filling & mt.ORDER_FILLING_IOC == mt.ORDER_FILLING_IOC:
        mode = mt.ORDER_FILLING_IOC
    else:
        mode = mt.ORDER_FILLING_RETURN
    
    
    req = {
        "action": mt.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": reqType,
        "price": price,
        "deviation": 10,
        "comment": "Auto Wifey (SJ)",
        "type_filling": mode, # mt.ORDER_FILLING_RETURN _FOK _IOC
        "type_time": mt.ORDER_TIME_DAY,
    }
    if positionID is not None: req["position"] = positionID
    
    return req

def sendRequest(request):
    # send a trading request
    logging.debug(request)
    result = mt.order_send(request)
    logging.error("last_error {}".format(mt.last_error()))
    #logging.info("retcode {}".format(result.retcode))
        
    if request["type"] == mt.ORDER_TYPE_BUY: 
        logging.info("order_send(): buy {} {} lots at {}".format(request["symbol"],request["volume"],request['price']))
    elif request["type"] == mt.ORDER_TYPE_SELL:
        logging.info("close position: sell {} {} lots at {} with deviation=none points".format(request["symbol"],request["volume"],request["price"]))
    
    # check the execution result
    if result.retcode != mt.TRADE_RETCODE_DONE:
        logging.error("order_send failed, retcode={}".format(result.retcode))
        logging.error("result %s",result)
        # request the result as a dictionary and display it element by element
        result_dict=result._asdict()
        for field in result_dict.keys():
            logging.error("   {}={}".format(field,result_dict[field]))
            # if this is a trading request structure, display it element by element as well
            if field=="request":
                traderequest_dict=result_dict[field]._asdict()
                for tradereq_filed in traderequest_dict:
                    logging.error("       traderequest: {}={}".format(tradereq_filed,traderequest_dict[tradereq_filed]))
        logging.info("shutdown() and quit")
        mt.shutdown()
        os._exit(0)
        
    if request["type"] == mt.ORDER_TYPE_BUY:
        logging.info("order_send done, ", result)
        logging.info("   opened position with POSITION_TICKET={}".format(result.order))
    elif request["type"] == mt.ORDER_TYPE_SELL:
        logging.info("position closed, {}".format(result))

def truncate_float(float_number, reference):
    
    multiplier = 10 ** decimal_places
    return int(float_number * multiplier) / multiplier

def UpdateAllosMT5(strategyTarget, investmentAmount):
    # Get your symbols for the entire strategy in a comma separated list
    group_input = ','.join(strategyTarget.keys())
    group_symbols=mt.symbols_get(group=group_input)
    positions=mt.positions_get(group=group_input)
    if len(group_symbols) != len(strategyTarget):
        logging.error("some symbols not found, check your mappings against your broker symbol names")
        mt.shutdown()
        os._exit(0)
    for pos in positions: 
        # Current position value (contract size multiplication pending later)
        strategyTarget[pos.symbol] = ApiData(strategyTarget[pos.symbol].targetAllo, pos, strategyTarget[pos.symbol].symbol, pos.volume * pos.price_current) 
        #strategyTarget[pos.symbol].append(pos.ticket)
        logging.info("Current position: %s", pos)
    
    for s in group_symbols:
        logging.info("symbol info (name, tick size, tick value, volume step) " + str(s.name) + ":" + str(s.trade_tick_size) +" " + str(s.trade_tick_value) +" " + str(s.volume_step))
        if(s.trade_contract_size == 0 or s.bid == 0 or s.ask == 0 or s.volume_min == 0 or s.volume_max == 0 or s.volume_step == 0):
            logging.error("tick size, value or volume step is zero: %s", s.name)
            mt.shutdown()
            os._exit(0)

        strategyTarget[s.name] = ApiData(strategyTarget[s.name].targetAllo, strategyTarget[s.name].position, s, strategyTarget[s.name].position_value * s.trade_contract_size)
        #strategyTarget[s.name][0].volume * strategyTarget[s.name][0].price_current * strategyTarget[s.name][1].trade_contract_size
        logging.debug(strategyTarget)
        
        if strategyTarget[s.name].position is not None:
            # nothing to do
            if strategyTarget[s.name].targetAllo - strategyTarget[s.name].position_value == 0:
                del strategyTarget[s.name]
                continue
            # SELL positions that get flipped between long and short
            if ((strategyTarget[s.name].position.type == mt.POSITION_TYPE_BUY and strategyTarget[s.name].targetAllo < 0) or 
                (strategyTarget[s.name].position.type == mt.POSITION_TYPE_SELL and strategyTarget[s.name].targetAllo > 0)):
                sendRequest(prepareRequest(s.name, strategyTarget[s.name].position.volume, "BUY" if strategyTarget[s.name].targetAllo > 0 else "SELL", strategyTarget[s.name].position.ticket, s.filling_mode))
                strategyTarget[s.name] = ApiData(strategyTarget[s.name].targetAllo, None, strategyTarget[s.name].symbol, 0) 
                continue
            # SELL positions that get reduced
            elif abs(strategyTarget[s.name].targetAllo) - strategyTarget[s.name].position_value < 0:
                lot = math.floor(( strategyTarget[s.name].position_value - abs(strategyTarget[s.name].targetAllo) ) / s.bid / s.trade_contract_size / s.volume_step ) * s.volume_step
                # math.floor(23000 / 3450 / 1 / .01 )* .01 
                logging.debug(lot)
                if lot < s.volume_min:
                    logging.info("closing difference smaller than min. lot size, not triggering a transaction for %s", s.name)
                    del strategyTarget[s.name]
                    continue
                if lot > s.volume_max:
                    logging.warn("exceeding max. closing lot size, closing only max lot size. Check your positions and investmentAmount!")
                    sendRequest(prepareRequest(s.name, s.volume_max, "BUY" if strategyTarget[s.name].targetAllo < 0 else "SELL", strategyTarget[s.name].position.ticket, s.filling_mode))
                    del strategyTarget[s.name]
                    continue
                
                sendRequest(prepareRequest(s.name, lot, "BUY" if strategyTarget[s.name].position.type == 1 else "SELL", strategyTarget[s.name].position.ticket, s.filling_mode))
                del strategyTarget[s.name]
                continue
                    
    # loop again from beginning, after first reducing positions, we have now capital to increase remaining positions        
    if len(strategyTarget) > 0: 
        for s in strategyTarget:
            # Is the allocation difference big enough to do something?
            lot = math.floor((abs(strategyTarget[s].targetAllo) - strategyTarget[s].position_value) / strategyTarget[s].symbol.bid / strategyTarget[s].symbol.trade_contract_size \
                / strategyTarget[s].symbol.volume_step) * strategyTarget[s].symbol.volume_step 
                        #  len(str(strategyTarget[s].symbol.volume_step).split('.')[1])
            if abs(lot) < strategyTarget[s].symbol.volume_min:
                    logging.debug(lot)
                    logging.info("opening difference smaller than min. lot size, not triggering a transaction for %s", s)
                    continue
            
            # We're doing something, so drop existing pos (if applicable) and rebuy at new size
            lot = math.floor(abs(strategyTarget[s].targetAllo) / strategyTarget[s].symbol.bid / strategyTarget[s].symbol.trade_contract_size \
                / strategyTarget[s].symbol.volume_step) * strategyTarget[s].symbol.volume_step
            # Close existing position before expanding
            if strategyTarget[s].position is not None:
                sendRequest(prepareRequest(s, strategyTarget[s].position.volume, "BUY" if strategyTarget[s].position.type == 1 else "SELL", strategyTarget[s].position.ticket, strategyTarget[s].symbol.filling_mode))
            if abs(lot) > strategyTarget[s].symbol.volume_max:
                    logging.warn("exceeding max. opening lot size, opening only max lot size. Lower your investmentAmount or allos won't follow the Wifey Strategy!")
                    sendRequest(prepareRequest(s, strategyTarget[s].symbol.volume_max, "BUY" if strategyTarget[s].targetAllo > 0 else "SELL", 0, strategyTarget[s].symbol.filling_mode))
                    continue

            sendRequest(prepareRequest(s, abs(lot), "BUY" if strategyTarget[s].targetAllo > 0 else "SELL", 0, strategyTarget[s].symbol.filling_mode)) 
    
    logging.info("Allos updated")     

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler) # if the process gets ended externally, clean up before exiting
    initMT()
    timeout = 30*60 # seconds (= 30 minutes (60s * 30m))
    timer = threading.Timer(timeout, cleanQuit, [True]) # shut the program down after the timeout, to make sure tomorrow's run is a fresh start
    timer.start()
    allos = receiveAllosIMAP(strategy, sender)

    strategyTarget = dict()
    ApiData = namedtuple('ApiData', ['targetAllo', 'position', 'symbol', 'position_value'])
    for allo in allos:
        if allo[0] != "USD": 
            if allo[0] not in symbolMap:
                logging.error("you need to define a mapping for symbol %s", allo[0])
                os._exit(0)
            strategyTarget[symbolMap[allo[0]]] = ApiData(float(investmentAmount) * float(allo[1]) / 100.0, None, None, 0)
    
    UpdateAllosMT5(strategyTarget, investmentAmount)
    #ShowFinalAllos() #TODO
    mt.shutdown()
    logging.info("All done, shutting down. Fingers crossed for market outperformance, may CQ be with you!")
    os._exit(0)
