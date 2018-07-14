import struct
from nulsexplorer.protocol.data import (BaseNulsData, NulsDigestData,
                                        write_with_length, read_by_length,
                                        writeUint48, readUint48,
                                        writeUint32, writeUint64,
                                        writeVarInt, hash_twice, VarInt,
                                        PLACE_HOLDER, ADDRESS_LENGTH, HASH_LENGTH)

class Coin(BaseNulsData):
    def __init__(self, data=None):
        self.address = None
        self.fromHash = None
        self.fromIndex = None
        self.na = None
        self.lockTime = None

        if data is not None:
            self.parse(data)

    def parse(self, buffer, cursor=0):
        owner = read_by_length(buffer, cursor)
        cursor += len(owner) + 1
        if len(owner) > ADDRESS_LENGTH:
            self.fromHash = owner[:-1]
            self.fromIndex = owner[-1]
        else:
            self.address = owner

        self.na = struct.unpack("Q", buffer[cursor:cursor+8])[0]
        cursor += 8
        self.lockTime = readUint48(buffer, cursor)
        cursor += 6
        return cursor

    def to_dict(self):
        val = {
            'value': self.na,
            'lockTime': self.lockTime
        }
        if self.address is not None:
            val['address'] = self.address.hex()

        if self.fromHash is not None:
            val['fromHash'] = self.fromHash.hex()
            val['fromIndex'] = self.fromIndex

        return val

    def __repr__(self):
        return "<UTXO Coin: {}: {} - {}>".format((self.address or self.fromHash).hex(), self.na, self.lockTime)

class CoinData(BaseNulsData):
    def __init__(self, data=None):
        self.from_count = None
        self.to_count = None
        self.inputs = list()
        self.outputs = list()

        if data is not None:
            self.parse(data)

    def parse(self, buffer, cursor=0):
        self.from_count = buffer[cursor]
        cursor += 1
        self.inputs = list()
        for i in range(self.from_count):
            coin = Coin()
            cursor = coin.parse(buffer, cursor)
            self.inputs.append(coin)

        self.to_count = buffer[cursor]
        cursor += 1
        self.outputs = list()
        for i in range(self.to_count):
            coin = Coin()
            cursor = coin.parse(buffer, cursor)
            self.outputs.append(coin)

        return cursor

    def get_fee(self):
        return sum([i.na for i in self.inputs]) - sum([o.na for o in self.outputs])

    def get_output_sum(self):
        return sum([o.na for o in self.outputs])

class Transaction(BaseNulsData):
    def __init__(self, data=None, height=None):
        self.type = None
        self.time = None
        self.hash = None
        self.height = height
        self.scriptSig = None
        self.module_data = dict()
        if data is not None:
            self.parse(data)

    def _parse_data(self, buffer, cursor=0):
        md = self.module_data
        if self.type == 1: # consensus reward
            cursor += len(PLACE_HOLDER)

        elif self.type == 2: # tranfer
            cursor += len(PLACE_HOLDER)

        elif self.type == 3: # alias
            md['address'] = read_by_length(buffer, cursor)
            cursor += len(md['address']) + 1

            md['alias'] = read_by_length(buffer, cursor)
            cursor += len(md['alias']) + 1
            md['alias'] = md['alias'].decode('utf-8')

        elif self.type == 4: # register agent
            md['deposit'] = struct.unpack("Q", buffer[cursor:cursor+8])[0]
            cursor += 8
            md['agentAddress'] = buffer[cursor:cursor+ADDRESS_LENGTH].hex()
            cursor += ADDRESS_LENGTH
            md['packingAddress'] = buffer[cursor:cursor+ADDRESS_LENGTH].hex()
            cursor += ADDRESS_LENGTH
            md['rewardAddress'] = buffer[cursor:cursor+ADDRESS_LENGTH].hex()
            cursor += ADDRESS_LENGTH
            md['commissionRate'] = struct.unpack("d", buffer[cursor:cursor+8])[0]
            cursor += 8
            return cursor

        elif self.type == 5: # join consensus
            md['deposit'] = struct.unpack("Q", buffer[cursor:cursor+8])[0]
            cursor += 8
            md['address'] = buffer[cursor:cursor+ADDRESS_LENGTH].hex()
            cursor += ADDRESS_LENGTH
            md['agentHash'] = buffer[cursor:cursor+HASH_LENGTH].hex()
            cursor += HASH_LENGTH

        elif self.type == 6: # cancel deposit
            md['joinTxHash'] = buffer[cursor:cursor+HASH_LENGTH].hex()
            cursor += HASH_LENGTH

        elif self.type == 7: # yellow card
            md['count'] = int(buffer[cursor])
            cursor += 1
            addresses = list()
            for i in range(md['count']):
                addresses.append(buffer[cursor:cursor+ADDRESS_LENGTH].hex())
                cursor += ADDRESS_LENGTH
            md['addresses'] = addresses

        elif self.type == 8: # red card
            md['address'] = read_by_length(buffer, cursor).hex()
            cursor += len(md['address']) + 1
            md['reason'] = buffer[cursor]
            cursor += 1
            md['evidence'] = read_by_length(buffer, cursor).hex()
            cursor += len(md['evidence']) + 1

        elif self.type == 9: # stop agent
            md['createTxHash'] = buffer[cursor:cursor+HASH_LENGTH]
            cursor += HASH_LENGTH

        return cursor

    def parse(self, buffer, cursor=0):
        st_cursor = cursor
        self.type = struct.unpack("H", buffer[cursor:cursor+2])[0]
        cursor += 2
        self.time = readUint48(buffer, cursor)
        cursor += 6


        st2_cursor = cursor

        self.remark = read_by_length(buffer, cursor)
        cursor += len(self.remark) + 1

        cursor = self._parse_data(buffer, cursor)

        self.coin_data = CoinData()
        cursor = self.coin_data.parse(buffer, cursor)
        med_cursor = cursor

        values = bytes((self.type,)) \
                + bytes((255,)) + writeUint64(self.time) \
                + buffer[st2_cursor:med_cursor]

        self.hash_bytes = hash_twice(values)
        self.hash = NulsDigestData(data=self.hash_bytes, alg_type=0)

        self.scriptSig = read_by_length(buffer, cursor)
        cursor += len(self.scriptSig) + 1
        end_cursor = cursor
        self.size = end_cursor - st_cursor

        return cursor


    def to_dict(self):
        return {
            'hash': str(self.hash),
            'type': self.type,
            'time': self.time,
            'blockHeight': self.height,
            'fee': self.coin_data.get_fee(),
            'remark': self.remark and self.remark.decode('utf-8') or None,
            'scriptSig': self.scriptSig and self.scriptSig.hex() or None,
            'size': self.size,
            'info': self.module_data,
            'inputs': [utxo.to_dict() for utxo in self.coin_data.inputs],
            'outputs': [utxo.to_dict() for utxo in self.coin_data.outputs]
        }
