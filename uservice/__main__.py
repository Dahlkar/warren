import asyncio
import uvloop
import uservice

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

if __name__ == "__main__":
    uservice.main()
