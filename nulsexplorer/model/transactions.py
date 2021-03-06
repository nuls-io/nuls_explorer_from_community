""" Transactions are generated from the block content.
"""

import pymongo
from nulsexplorer.model.base import BaseClass, Index
from pymongo import UpdateOne

import logging
import operator
LOGGER = logging.getLogger('model.transactions')

class Transaction(BaseClass):
    COLLECTION = "transactions"

    INDEXES = [Index("hash", unique=True),
               Index([("blockHeight", pymongo.ASCENDING)]),
               Index([("blockHeight", pymongo.DESCENDING)]),
               Index([("time", pymongo.DESCENDING)]),
               Index("type"),
               Index("outputs.address"),
               Index("inputs.address"),
               #Index("outputs.status"),
               #Index("outputs.lockTime"),
               Index("info.createTxHash"),
               Index("info.agentHash"),
               Index("info.contractAddress"),
               Index("info.result.success"),
               Index("info.aggregate.key"),
               Index("info.type"),
               Index("info.post.type"),
               Index("info.post.ref"),
               Index("info.post.content.tags"),
               Index([("time", pymongo.DESCENDING),
                      ("type", pymongo.ASCENDING)]),
               #Index([("outputs.status", pymongo.ASCENDING),
               #       ("outputs.lockTime", pymongo.ASCENDING)]),
               Index([("outputs.status", pymongo.DESCENDING),
                      ("outputs.lockTime", pymongo.ASCENDING)]),
               Index([("type", pymongo.ASCENDING),
                      ("inputs.address", pymongo.ASCENDING)]),
               Index([("type", pymongo.ASCENDING),
                      ("outputs.address", pymongo.ASCENDING)])]

    @classmethod
    async def update_locks(cls, block_height):
        """ Sets all unspent locked outputs with a lock time in the past to unlocked.
        """
        LOGGER.info("Unlocking transaction on block %d" % block_height)
        await cls.collection.update_many(
            {'$and': [
                {'outputs.status': 1},
                {'outputs.lockTime': {'$lt': block_height}},
                {'outputs.lockTime': {'$ne': -1}}]},
            {'$set': {"outputs.$[].status": 0}})

    @classmethod
    async def input_txdata(cls, tx_data, batch_mode=False,
                           batch_transactions=None):
        #await cls.collection.insert(tx_data)
        transaction = tx_data
        collec = cls.collection

        if transaction['type'] == 6:
            join_tx_hash = transaction['info'].get('joinTxHash', None)
            if join_tx_hash is not None:
                if batch_mode and (join_tx_hash in batch_transactions):
                    join_tx = batch_transactions[join_tx_hash]
                else:
                    join_tx = await collec.find_one(dict(hash=join_tx_hash))
                transaction['info']['address'] = join_tx['info']['address']
                transaction['info']['agentHash'] = join_tx['info']['agentHash']


        bulk_updates = []
        if len(transaction['inputs']):
            LOGGER.info("Handling inputs")

            source_txs = {}
            ihashes = [idata['fromHash'] for idata in transaction['inputs']]
            itxs = collec.find({'hash': {'$in': ihashes}},
                                    projection=['hash', 'outputs'])
            async for itx in itxs:
                source_txs[itx['hash']] = itx


        for i, inputdata in enumerate(transaction['inputs']):
            fhash = inputdata['fromHash']
            fidx = inputdata['fromIndex']
            source_tx = None
            if batch_mode and batch_transactions is not None:
                source_tx = batch_transactions.get(fhash, None)
                if source_tx is not None:
                    source_output = source_tx['outputs'][fidx]
                    source_output['status'] = 3
                    source_output['toHash'] = transaction['hash']
                    source_output['toIndex'] = i

            if source_tx is None:
                # source_tx = await collec.find_one(
                #     dict(hash=fhash),
                #     projection=['outputs'])
                source_tx = source_txs.get(fhash, None)
                if source_tx is None:
                    LOGGER.warning("Source tx not found %s" % fhash)
                bulk_updates.append(
                    UpdateOne(dict(hash=fhash),
                              {'$set': {
                                    ('outputs.%d.status' % fidx): 3,
                                    ('outputs.%d.toHash' % fidx): transaction['hash'],
                                    ('outputs.%d.toIndex' % fidx): i
                              }}))

            if source_tx is not None:
                in_from = source_tx['outputs'][inputdata['fromIndex']]
                inputdata['address'] = in_from['address']
            #     in_from['status'] = 3
            #     in_from['toHash'] = transaction.hash
            #     in_from['toIndex'] = i
            #     await source_tx.save()

        if len(bulk_updates):
            result = await collec.bulk_write(bulk_updates, ordered=False)
            LOGGER.debug("Bulk write")

        for outputdata in transaction['outputs']:
            if 'status' not in outputdata:
                lockTime = outputdata.get("lockTime", 0)
                if lockTime > 0:
                    outputdata['status'] = 1
                elif lockTime == -1:
                    outputdata['status'] = 2
                else:
                    outputdata['status'] = 0
        if batch_mode:
            return transaction
        else:
            try:
                await collec.insert_one(tx_data)
            except pymongo.errors.DuplicateKeyError:
                LOGGER.warning("Transaction %s was already there" % transaction['hash'])
