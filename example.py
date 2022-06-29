import asyncio
import aiohttp

from custom_components.coverflex.api import CoverflexAPI

async def main():
    async with aiohttp.ClientSession() as session:
        api = CoverflexAPI(session)

        username = input("Enter your username/email..: ")
        password = input("Enter your password........: ")

        token = await api.login(username, password)
        if (token):
            card = await api.getCard(token)
            print ("Card...................:", card)
            print ("  Card Id..............:", card.id)
            print ("  Activated at.........:", card.activated_at)
            print ("  Expiration Date......:", card.expiration_date)
            print ("  Holder Company Name..:", card.holder_company_name)
            print ("  Holder Name..........:", card.holder_name)
            print ("  Card Status..........:", card.status)

            pocket = await api.getBalance(token)
            print ("  Balance..............:", pocket.balance)
            print ("  Currency.............:", pocket.currency)

            # printTransaction = input("Print transaction list? (y/N) ")
            # if (printTransaction == "Y" or printTransaction == "y"):                    
            #     [print ("  -", t.date, t.name, t.amount) 
            #         for t in account.movementList]

asyncio.get_event_loop().run_until_complete(main())