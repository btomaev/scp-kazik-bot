from aiogram import Router
from aiogram.filters import CommandStart, Command


from . import start
from . import dep
from . import state
from . import admin

def prepare_router() -> Router:
    router = Router()
    router.message.register(start.start, CommandStart())

    router.message.register(dep.slot, Command('slot'))
    router.message.register(dep.dep, Command('dep'))
    router.message.register(dep.loan, Command('loan'))
    
    router.message.register(state.balance, Command('balance'))
    router.message.register(state.stats, Command('stats'))

    router.message.register(admin.admit_chat, Command('admit_chat'))
    router.message.register(admin.deny_chat, Command('deny_chat'))


    return router