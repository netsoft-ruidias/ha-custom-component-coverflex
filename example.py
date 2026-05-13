import asyncio
import os
import aiohttp
from pathlib import Path
from dotenv import load_dotenv

from custom_components.coverflex.api import CoverflexAPI
from custom_components.coverflex.exceptions import OTPRequiredException

load_dotenv()

DEVICE_TOKEN_FILE = Path(".coverflex_device_token")
REFRESH_TOKEN_FILE = Path(".coverflex_refresh_token")


def load_device_token() -> str | None:
    if DEVICE_TOKEN_FILE.exists():
        token = DEVICE_TOKEN_FILE.read_text().strip()
        return token or None
    return None


def save_device_token(token: str) -> None:
    DEVICE_TOKEN_FILE.write_text(token)


def load_refresh_token() -> str | None:
    if REFRESH_TOKEN_FILE.exists():
        token = REFRESH_TOKEN_FILE.read_text().strip()
        return token or None
    return None


def save_refresh_token(token: str) -> None:
    REFRESH_TOKEN_FILE.write_text(token)


async def main():
    """Test the API client."""
    connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector) as session:
        api = CoverflexAPI(session)

        username_input = input("Enter your username/email..: ").strip()
        password_input = input("Enter your password........: ").strip()

        username = username_input or os.getenv("COVERFLEX_USERNAME", "")
        password = password_input or os.getenv("COVERFLEX_PASSWORD", "")

        if not username or not password:
            print("Missing credentials. Provide input values or set COVERFLEX_USERNAME/COVERFLEX_PASSWORD in .env")
            return

        # 1. Try refresh token first (fastest, no SMS needed)
        token = None
        refresh_token = load_refresh_token()
        if refresh_token:
            print("Refresh token found, attempting silent token renewal...")
            renewed = await api.refresh_access_token(refresh_token)
            if renewed and renewed.get("access_token"):
                token = renewed["access_token"]
                save_refresh_token(renewed["refresh_token"])
                print("Token renewed successfully.")
            else:
                print("Refresh token expired, falling back to login...")

        # 2. Try login with device token (skip OTP)
        if not token:
            device_token = load_device_token()
            if device_token:
                print("Device token found, attempting login without OTP...")
            try:
                token = await api.login(username, password, user_agent_token=device_token)
            except OTPRequiredException as e:
                print(f"OTP required via {e.otp_channel} (last digits: ****{e.phone_last_digits})")
                otp_code = input("Enter the OTP code............: ")
                token = await api.login_with_otp(username, password, otp_code)
                if token:
                    trust = await api.get_trust_token(token)
                    if trust:
                        save_device_token(trust["user_agent_token"])
                        save_refresh_token(trust["refresh_token"])
                        token = trust["access_token"]
                        print("Device + refresh tokens saved — future logins will skip OTP.")
                    else:
                        print("Warning: could not obtain device trust token.")

        if token:
            card = await api.get_card(token)
            print("Card...................:", card)
            print("  Card Id..............:", card.id)
            print("  Activated at.........:", card.activated_at)
            print("  Expiration Date......:", card.expiration_date)
            print("  Holder Company Name..:", card.holder_company_name)
            print("  Holder Name..........:", card.holder_name)
            print("  Card Status..........:", card.status)

            pockets = await api.get_balances(token)
            if pockets:
                print(f"  Pockets ({len(pockets)}):")
                for pocket in pockets:
                    print(f"    [{pocket.type}] Balance: {pocket.balance} {pocket.currency}")

                get_transactions = input("Get transaction list? (y/N) ")
                if get_transactions.lower() == "y":
                    for pocket in pockets:
                        print(f"\n  Transactions for pocket [{pocket.type}]:")
                        transactions = await api.get_movements(token, pocket.id, 10)
                        if transactions:
                            for t in transactions:
                                print(f"    - {t.date} {t.description} {t.amount} {t.currency}")
                        else:
                            print("    (no transactions)")


asyncio.run(main())
