from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import json
import decimal
import rlp
from eth_typing import HexStr
from eth_utils import to_bytes
from ethereum.transactions import Transaction
import time
from lamden.crypto.wallet import Wallet
from lamden.crypto.transaction import build_transaction
from contracting.db.encoder import decode

class CustomHandler(BaseHTTPRequestHandler):
    masternode_lamden = "https://masternode-01.lamden.io"

    # we need something better then these maps. some kind of converter that produces exact results
    # lamden seed phrase = ethereum seed phrase maybe possibru
    lamden_eth_map = {
        "ff61544ea94eaaeb5df08ed863c4a938e9129aba6ceee5f31b6681bdede11b89": "0x70cbf2c569917993ead738e54894557b44dbff5e",
        "80b5984b24261207ccb9b82b24a420a4f250f10f3a462abe1514afaa0e0eb376" : "0x7c569034fee3657461f27ef101d6460b24f9bad6"
    }

    eth_lamden_map = {
        "0x70cbf2c569917993ead738e54894557b44dbff5e" : "ff61544ea94eaaeb5df08ed863c4a938e9129aba6ceee5f31b6681bdede11b89",
        "0x7c569034fee3657461f27ef101d6460b24f9bad6" : "80b5984b24261207ccb9b82b24a420a4f250f10f3a462abe1514afaa0e0eb376"
    }

    def hex_to_bytes(self, data: str) -> bytes:
        return to_bytes(hexstr=HexStr(data))

    def getLastBlockNumberAsHex(self):
        latest_block_json = requests.get(self.masternode_lamden + "/latest_block", headers={
                                         'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36'}, timeout=2)
        latest_block = hex(json.loads(latest_block_json.text)["number"])
        return latest_block

    def getBlockData(self, block_number):
        block_number = int(block_number, 0)
        block_json = requests.get(self.masternode_lamden + "/blocks?num=" + str(block_number), headers={
                                  'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36'}, timeout=2)
        block = json.loads(block_json.text)
        transactions = []
        for tx in block["subblocks"][0]["transactions"]:  # fix this for multiple subblocks
            transactions.append(tx["hash"])
        block["transactions_for_rpc"] = transactions
        return block

    def getBalanceByETHAddress(self, eth_address):
        try:
            lamden_address = self.eth_lamden_map[eth_address]
            currency_balance_json = requests.get(self.masternode_lamden + "/contracts/currency/balances?key=" + lamden_address, headers={
                                                 'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36'}, timeout=2)
            currency_balance = json.loads(currency_balance_json.text)[
                "value"]["__fixed__"]
        except:
            currency_balance = "0.00000000"
        return hex(int(decimal.Decimal(currency_balance)*pow(10, 18)))

    def getNonce(self, lamden_address):
        try:
            currency_balance_json = requests.get(self.masternode_lamden + "/nonce/" + lamden_address, headers={
                                                 'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36'}, timeout=2)
            nonce = decode(currency_balance_json.text)
        except:
            nonce = 0
        return nonce
    
    def EcDsaSignatureToLamdenSignature(self, eth_tx, lamden_tx):
        print(eth_tx)
        print(lamden_tx)
        transaction = {
            'contract': lamden_tx["payload"]["contract"],
            'function': lamden_tx["payload"]["function"],
            'kwargs': lamden_tx["payload"]["kwargs"],
            'sender': lamden_tx["payload"]["sender"],
            'stamps_supplied': lamden_tx["payload"]["stamps_supplied"],
            'nonce': lamden_tx["payload"]["nonce"],
            'processor': lamden_tx["payload"]["processor"]
        }
        
        #wallet = Wallet(seed = bytes.fromhex('PRIVKEY'))
        signature = wallet.sign(json.dumps(transaction))
        return signature
        #return None

    def convertEthereumTransactionToLamden(self, tx):
        # we need to build tx from decoded eth tx
        #lamden_tx = {}
        #lamden_tx["metadata"] = {}
        #lamden_tx["metadata"]["timestamp"] = int(time.time())

        #lamden_tx["payload"] = {}
        #lamden_tx["payload"]["contract"] = "currency"
        #lamden_tx["payload"]["function"] = "transfer"

        #lamden_tx["payload"]["kwargs"] = {}
        #lamden_tx["payload"]["kwargs"]["amount"] = {"__fixed__": str(tx["value"] / pow(10, 18))}
        #lamden_tx["payload"]["kwargs"]["to"] = self.eth_lamden_map[tx["to"]]

        #lamden_tx["payload"]["nonce"] = self.getNonce(tx["sender"])
        #lamden_tx["payload"]["processor"] = "89f67bb871351a1629d66676e4bd92bbacb23bd0649b890542ef98f1b664a497"
        #lamden_tx["payload"]["sender"] = self.eth_lamden_map[tx["sender"]]
        #lamden_tx["payload"]["stamps_supplied"] = 200  # use gas calc later

        #signature = self.EcDsaSignatureToLamdenSignature(tx, lamden_tx)
        #lamden_tx["metadata"]["signature"] = signature

        #lamden_tx_json = (json.dumps(lamden_tx))

        wallet = Wallet(seed = bytes.fromhex('PRIVKEY HERE'))

        tx_kwargs = {
                "amount": decimal.Decimal(tx["value"] / pow(10, 18)),
                "to" : self.eth_lamden_map[tx["to"]]
            }

        nonce = self.getNonce(self.eth_lamden_map[tx["sender"]])
        lamden_tx_json = build_transaction(
                wallet=wallet,
                processor=nonce["processor"],
                stamps=200,
                nonce=nonce["nonce"],
                contract='currency',
                function='transfer',
                kwargs=tx_kwargs)

        response_lamden = requests.post(
            self.masternode_lamden, data=lamden_tx_json, headers={
                'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36'}, timeout=2)
        return json.loads(response_lamden.text)["hash"]

    def buildResponse(self, data):
        response_dict = {}
        if(data["method"] == "eth_chainId"):
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            response_dict["result"] = "0x239"  # chain id
        if(data["method"] == "eth_getBalance"):
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            response_dict["result"] = self.getBalanceByETHAddress(
                data["params"][0].lower())  # address balance
        if(data["method"] == "eth_blockNumber"):
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            # last block
            response_dict["result"] = self.getLastBlockNumberAsHex()
        if(data["method"] == "eth_getBlockByNumber"):
            block_number = data["params"][0]
            block = self.getBlockData(block_number)
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            response_dict["result"] = {
                "difficulty": "0x0",
                "extraData": "0x0",
                "gasLimit": "0x0",
                "gasUsed": "0x0",
                "hash": block["hash"],
                "logsBloom": "0x0",
                "miner": "0x0",
                "mixHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "nonce": "0x0",
                "number": block_number,
                "parentHash": block["previous"],
                "receiptsRoot": "0x0",
                "sha3Uncles": "0x0",
                "size": "0x0",
                "stateRoot": "0x0",
                "timestamp": "0x0",
                "totalDifficulty": "0x0",
                "transactions": block["transactions_for_rpc"],
                "transactionsRoot": "0x0",
                "uncles": []
            }  # Full Block
        if(data["method"] == "eth_gasPrice"):
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            response_dict["result"] = "0x0"  # Gas Price
        if(data["method"] == "eth_estimateGas"):
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            # Gas needs to be 21000 or Metamask will error (I think we can make the final fee calc work with some math)
            response_dict["result"] = "0x5208"
        if(data["method"] == "eth_getCode"):
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            # Not sure, some code of the given address (not needed, skip this for now)
            response_dict["result"] = "0x0"
        if(data["method"] == "eth_getTransactionCount"):
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            # Amount of TXs sent from this address = nonce, we dont need
            response_dict["result"] = "0x1"
        if(data["method"] == "eth_sendRawTransaction"):
            # decode tx
            raw_tx = rlp.decode(self.hex_to_bytes(data["params"][0]), Transaction)
            tx = raw_tx.to_dict()
            lamden_tx = self.convertEthereumTransactionToLamden(tx)
            response_dict["jsonrpc"] = "2.0"
            response_dict["id"] = data["id"]
            response_dict["result"] = lamden_tx  # TX Hash
        if(data["method"] == "eth_call"):  # (not needed, skip this for now)
            pass
        response = (json.dumps(response_dict)).encode('utf-8')
        print("Response: " + str(response))
        self.wfile.write(response)

    def setHeaders(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    # ETH RPC ONLY POST REQUESTS USED
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_json = self.rfile.read(content_length).decode('utf-8')
        post_data = json.loads(post_json)
        print("Request: " + post_data["method"] +
              " with Parameters: " + str(post_data["params"]))
        self.setHeaders()
        self.buildResponse(post_data)


with HTTPServer(('', 8000), CustomHandler) as server:
    server.serve_forever()
