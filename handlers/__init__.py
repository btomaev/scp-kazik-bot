from aiogram import F, Router
from aiogram.filters import CommandStart, Command

from handlers import blackjack
from keyboards.blackjack import BlackjackCallback

from . import start
from . import dep
from . import slot
from . import state
from . import admin

def prepare_router() -> Router:
    router = Router()
    router.message.register(start.start, CommandStart())

    router.message.register(admin.admit_chat, Command('admit_chat'))
    router.message.register(admin.deny_chat, Command('deny_chat'))
    router.message.register(admin.set_balance, Command('set_balance'))
    router.message.register(admin.change_balance, Command('change_balance'))
    router.message.register(admin.set_debt, Command('set_debt'))

    router.message.register(state.balance, Command('balance'))
    router.message.register(state.stats, Command('stats'))

    router.message.register(dep.dep, Command('dep'))
    router.message.register(dep.loan, Command('loan'))
    
    router.message.register(slot.slot, Command('slot'))
    router.message.register(blackjack.blackjack, Command('blackjack'))


    router.callback_query.register(blackjack.create_room, BlackjackCallback.filter(F.action == 'create'))
    router.callback_query.register(blackjack.join_room, BlackjackCallback.filter(F.action == 'join'))
    router.callback_query.register(blackjack.exit_room, BlackjackCallback.filter(F.action == 'exit'))
    router.callback_query.register(blackjack.start_room, BlackjackCallback.filter(F.action == 'start'))
    router.callback_query.register(blackjack.show_controls, BlackjackCallback.filter(F.action == 'controls'))
    router.callback_query.register(blackjack.action_hit, BlackjackCallback.filter(F.action == 'hit'))
    router.callback_query.register(blackjack.action_stand, BlackjackCallback.filter(F.action == 'stand'))

    return router
