from flask import Flask, request, g
from flask_restful import Resource, Api
from sqlalchemy import create_engine
from flask import jsonify
import json
import eth_account
import algosdk
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import load_only
from datetime import datetime
import math
import sys
import traceback

# TODO: make sure you implement connect_to_algo, send_tokens_algo, and send_tokens_eth
from send_tokens import connect_to_algo, connect_to_eth, send_tokens_algo, send_tokens_eth

from models import Base, Order, TX, Log
engine = create_engine('sqlite:///orders.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

app = Flask(__name__)

""" Pre-defined methods (do not need to change) """

@app.before_request
def create_session():
    g.session = scoped_session(DBSession)

@app.teardown_appcontext
def shutdown_session(response_or_exc):
    sys.stdout.flush()
    g.session.commit()
    g.session.remove()

def connect_to_blockchains():
    try:
        # If g.acl has not been defined yet, then trying to query it fails
        acl_flag = False
        g.acl
    except AttributeError as ae:
        acl_flag = True
    
    try:
        if acl_flag or not g.acl.status():
            # Define Algorand client for the application
            g.acl = connect_to_algo()
    except Exception as e:
        print("Trying to connect to algorand client again")
        print(traceback.format_exc())
        g.acl = connect_to_algo()
    
    try:
        icl_flag = False
        g.icl
    except AttributeError as ae:
        icl_flag = True
    
    try:
        if icl_flag or not g.icl.health():
            # Define the index client
            g.icl = connect_to_algo(connection_type='indexer')
    except Exception as e:
        print("Trying to connect to algorand indexer client again")
        print(traceback.format_exc())
        g.icl = connect_to_algo(connection_type='indexer')

        
    try:
        w3_flag = False
        g.w3
    except AttributeError as ae:
        w3_flag = True
    
    try:
        if w3_flag or not g.w3.isConnected():
            g.w3 = connect_to_eth()
    except Exception as e:
        print("Trying to connect to web3 again")
        print(traceback.format_exc())
        g.w3 = connect_to_eth()
        
""" End of pre-defined methods """
        
""" Helper Methods (skeleton code for you to implement) """

def log_message(message_dict):
    msg = json.dumps(message_dict)

    # TODO: Add message to the Log table
    new_log = Log( message=message_dict )

    g.session.add(new_log)
    g.session.commit()
    
    return

def get_algo_keys():
    
    # TODO: Generate or read (using the mnemonic secret) 
    # the algorand public/private keys
    
    return algo_sk, algo_pk


def get_eth_keys(filename = "eth_mnemonic.txt"):
    w3 = Web3()

    # TODO: Generate or read (using the mnemonic secret) 
    # the ethereum public/private keys
    mnemonic_secret = "chilly bite brash slim baseball quick sack support cloudy ignorant tangible invincible actually attack past hands drown work paint sparkling whispering balance absent meddle"
    acct = w3.eth.account.from_mnemonic(mnemonic_secret)
    eth_pk = acct._address
    eth_sk = acct._private_key

    return eth_sk, eth_pk
  
def fill_order(order, txes=[]):
    # TODO: 
    # Match orders (same as Exchange Server II)
    # Validate the order has a payment to back it (make sure the counterparty also made a payment)
    # Make sure that you end up executing all resulting transactions!

    # If your fill_order function is recursive, and you want to have fill_order return a list of transactions to be filled, 
    # Then you can use the "txes" argument to pass the current list of txes down the recursion
    # Note: your fill_order function is *not* required to be recursive, and it is *not* required that it return a list of transactions, 
    # but executing a group of transactions can be more efficient, and gets around the Ethereum nonce issue described in the instructions
    
    # Check if there are any existing orders that match
    query = (g.session.query(Order)
              .filter(Order.filled == None)
              .filter(Order.buy_currency == order.sell_currency)
              .filter(Order.sell_currency == order.buy_currency)
              .filter((Order.sell_amount/Order.buy_amount) >= (order.buy_amount/order.sell_amount))
            )
    
    # Inserting order in database
    new_order = Order( sender_pk=order.sender_pk,
        receiver_pk=order.receiver_pk, 
        buy_currency=order.buy_currency, 
        sell_currency=order.sell_currency, 
        buy_amount=order.buy_amount, 
        sell_amount=order.sell_amount )
    g.session.add(new_order)
    g.session.commit()
    
    if query.count() > 0:
        existing_order = query.first()
      
        # Set the filled field to be the current timestamp on both orders
        new_order.filled = datetime.now()
        existing_order.filled = datetime.now()
        g.session.commit()
      
        # Set counterparty_id to be the id of the other order
        new_order.counterparty_id = existing_order.id
        existing_order.counterparty_id = new_order.id
        g.session.commit()
      
        # If one of the orders is not completely filled 
        # (i.e. the counterparty’s sell_amount is less than buy_amount)
        if new_order.buy_amount < existing_order.sell_amount:
            remaining_buy = existing_order.sell_amount - new_order.buy_amount
            remaining_sell = existing_order.buy_amount - new_order.sell_amount
        
            if (remaining_buy > 0  and remaining_sell > 0 and ()):
                derived_order = Order( sender_pk=existing_order.sender_pk,
                    receiver_pk=existing_order.receiver_pk, 
                    buy_currency=existing_order.buy_currency, 
                    sell_currency=existing_order.sell_currency, 
                    buy_amount=remaining_sell, 
                    sell_amount=remaining_buy,
                    creator_id=existing_order.id)
                g.session.add(derived_order)
                g.session.commit()
      
        elif new_order.buy_amount > existing_order.sell_amount:
            remaining_buy = new_order.buy_amount - existing_order.sell_amount
            remaining_sell = new_order.sell_amount - existing_order.buy_amount
        
            if (remaining_buy > 0  and remaining_sell > 0):
                derived_order = Order( sender_pk=new_order.sender_pk,
                    receiver_pk=new_order.receiver_pk, 
                    buy_currency=new_order.buy_currency, 
                    sell_currency=new_order.sell_currency, 
                    buy_amount=remaining_buy, 
                    sell_amount=remaining_sell,
                    creator_id=new_order.id)
                g.session.add(derived_order)
                g.session.commit()
    pass
  
def execute_txes(txes):
    if txes is None:
        return True
    if len(txes) == 0:
        return True
    print( f"Trying to execute {len(txes)} transactions" )
    print( f"IDs = {[tx['order_id'] for tx in txes]}" )
    eth_sk, eth_pk = get_eth_keys()
    algo_sk, algo_pk = get_algo_keys()
    
    if not all( tx['platform'] in ["Algorand","Ethereum"] for tx in txes ):
        print( "Error: execute_txes got an invalid platform!" )
        print( tx['platform'] for tx in txes )

    algo_txes = [tx for tx in txes if tx['platform'] == "Algorand" ]
    eth_txes = [tx for tx in txes if tx['platform'] == "Ethereum" ]

    # TODO: 
    #       1. Send tokens on the Algorand and eth testnets, appropriately
    #          We've provided the send_tokens_algo and send_tokens_eth skeleton methods in send_tokens.py
    #       2. Add all transactions to the TX table

    pass

""" End of Helper methods"""
  
@app.route('/address', methods=['POST'])
def address():
    if request.method == "POST":
        content = request.get_json(silent=True)
        if 'platform' not in content.keys():
            print( f"Error: no platform provided" )
            return jsonify( "Error: no platform provided" )
        if not content['platform'] in ["Ethereum", "Algorand"]:
            print( f"Error: {content['platform']} is an invalid platform" )
            return jsonify( f"Error: invalid platform provided: {content['platform']}"  )
        
        if content['platform'] == "Ethereum":
            #Your code here
            return jsonify( eth_pk )
        if content['platform'] == "Algorand":
            #Your code here
            return jsonify( algo_pk )

@app.route('/trade', methods=['POST'])
def trade():
    print( "In trade", file=sys.stderr )
    connect_to_blockchains()
    get_keys()
    if request.method == "POST":
        content = request.get_json(silent=True)
        columns = [ "buy_currency", "sell_currency", "buy_amount", "sell_amount", "platform", "tx_id", "receiver_pk"]
        fields = [ "sig", "payload" ]
        error = False
        for field in fields:
            if not field in content.keys():
                print( f"{field} not received by Trade" )
                error = True
        if error:
            print( json.dumps(content) )
            return jsonify( False )
        
        error = False
        for column in columns:
            if not column in content['payload'].keys():
                print( f"{column} not received by Trade" )
                error = True
        if error:
            print( json.dumps(content) )
            return jsonify( False )
        
        # Your code here
        # 1. Check the signature
        # 2. Add the order to the table
        # 3a. Check if the order is backed by a transaction equal to the sell_amount (this is new)
        # 3b. Fill the order (as in Exchange Server II) if the order is valid
        # 4. Execute the transactions
        # If all goes well, return jsonify(True). else return jsonify(False)

        result = False #Should only be true if signature validates
        sig = content['sig']
        payload = content['payload']
        payload_str = json.dumps(payload)

        if payload['platform'] == 'Ethereum':
            # Generating Ethereum account
            eth_account.Account.enable_unaudited_hdwallet_features()
            acct, mnemonic = eth_account.Account.create_with_mnemonic()
            eth_pk = acct.address
            eth_sk = acct.key

            eth_encoded_msg = eth_account.messages.encode_defunct(text=payload_str)
            if eth_account.Account.recover_message(eth_encoded_msg,signature=content['sig']) == payload['sender_pk']:
                result = True
        
        elif payload['platform']  == 'Algorand':
            print('algorand')
            if algosdk.util.verify_bytes(payload_str.encode('utf-8'),content['sig'],payload['sender_pk']):
                result = True
        
        if result == True:
            new_order = Order( sender_pk=payload['sender_pk'],
                receiver_pk=payload['receiver_pk'], 
                buy_currency=payload['buy_currency'], 
                sell_currency=payload['sell_currency'], 
                buy_amount=payload['buy_amount'], 
                sell_amount=payload['sell_amount'],
                signature=content['sig'] )
            fill_order(new_order)
            g.session.add(new_order)
            g.session.commit()
        else:
            log_message(json.dumps(payload))

        return jsonify( True )

@app.route('/order_book')
def order_book():
    # Same as before
    data = []
    
    query = (g.session.query(Order).all())

    for order in query:
        temp_dict = {}

        temp_dict['sender_pk'] = order.sender_pk
        temp_dict['receiver_pk'] = order.receiver_pk
        temp_dict['buy_currency'] = order.buy_currency
        temp_dict['sell_currency'] = order.sell_currency
        temp_dict['buy_amount'] = order.buy_amount
        temp_dict['sell_amount'] = order.sell_amount
        temp_dict['signature'] = order.signature

        data.append(temp_dict)
        g.session.commit()
    
    reponse = {'data': data}

    return jsonify(reponse)

if __name__ == '__main__':
    app.run(port='5002')
