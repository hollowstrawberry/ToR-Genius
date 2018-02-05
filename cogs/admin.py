# Original work Copyright (c) 2015 Rapptz (https://github.com/Rapptz/RoboDanny)
# Original work Copyright (c) 2017 khazhyk (https://github.com/khazhyk/dango.py)
# Modified work Copyright (c) 2017 Perry Fraser
#
# Licensed under the MIT License. https://opensource.org/licenses/MIT

# All of Admin class except for some formatting and other small details
# from R. Danny

# sh command and run_subprocess from dango.py

import asyncio
import copy
import inspect
import io
import random
import subprocess
import textwrap
import traceback
from contextlib import redirect_stdout

import aiohttp
import discord
from discord.ext import commands

from cogs.utils.context import Context


async def run_subprocess(cmd, loop=None):
    # https://github.com/khazhyk/dango.py/blob/master/plugins/common/utils.py#L45-L55
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        res = await proc.communicate()
    except NotImplementedError:
        loop = loop or asyncio.get_event_loop()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        res = await loop.run_in_executor(None, proc.communicate)
    return [s.decode('utf8') for s in res]


async def haste_upload(text):
    text = str(text)
    with aiohttp.ClientSession() as session:
        async with session.post('https://hastebin.com/documents/', data=text,
                                headers={'Content-Type': 'text/plain'}) as r:
            r = await r.json()
            return r['key']


async def gist_upload(files, public=False, description=''):
    description = str(description)
    data = {
        'description': description,
        'public': public,
        'files': files
    }
    with aiohttp.ClientSession() as session:
        async with session.post('https://api.github.com/gists', json=data) as r:
            json = await r.json()
            return json['html_url']


class Admin:
    """Admin only commands for the PWNZ"""

    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
        self.sessions = set()
        self.messages = {}

    @staticmethod
    def cleanup_code(content):
        """
        Automatically removes code blocks from the code. This is for when
        using the eval stuff, you type in a code block, and it removes it for
        you. Magic!
        """
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    async def on_message_edit(self, before, after):
        result = self.messages.get(before.id)
        if not result:
            return

        trigger, resp = result
        await resp.delete()
        await self.bot.process_commands(after)

    async def send_response(self, ctx, content, inp, extra=None,
                            file_type='py', raw=False):

        if extra is None:
            if content:
                try:
                    m = await ctx.send(
                        content if raw else f'```{file_type}\n{content}\n```'
                    )
                    self.messages[ctx.message.id] = (ctx.message, m)
                except discord.HTTPException:
                    key = await gist_upload(
                        {f'in.{file_type}': {'content': inp},
                         f'out.{file_type}': {'content': content}})
                    m = await ctx.send(key)
                    self.messages[ctx.message.id] = (ctx.message, m)

        else:
            self._last_result = extra
            try:
                m = await ctx.send(
                    content if raw else f'```{file_type}\n{content}{extra}\n```'
                )
                self.messages[ctx.message.id] = (ctx.message, m)
            except discord.HTTPException:
                key = await gist_upload(
                    {f'in.{file_type}': {'content': inp},
                     f'out.{file_type}': {'content': content + extra}})
                m = await ctx.send(key)
                self.messages[ctx.message.id] = (ctx.message, m)

    async def __local_check(self, ctx):
        k = await self.bot.is_owner(ctx.author)
        if not k:
            # await ctx.send("I honestly don't know _why_ you thought that "
            #                "would work, but ok.")
            return False

        return True

    @staticmethod
    def get_syntax_error(e):
        if e.text is None:
            return f'```py\n{e.__class__.__name__}: {e}\n```'
        return f'```py\n{e.text}{"^":>{e.offset}}\n{e.__class__.__name__}:' \
               f' {e}```'

    @commands.command(hidden=True)
    async def sh(self, ctx, *, cmd):
        # https://github.com/khazhyk/dango.py/blob/master/plugins/debug.py#L144-L153
        await ctx.channel.trigger_typing()
        sout, serr = await run_subprocess(cmd)

        out = ""

        if sout:
            out = f'Stdout: ```{sout}```'

        if serr:
            out = f'Stderr: ```{serr}```\n\n\n' + out

        # try:
        #     await ctx.send(out if out else ":ok_hand:")
        # except discord.HTTPException:
        #     key = await gist_upload({'out.sh': {'content': out}})
        #     await ctx.send(key)

        await self.send_response(ctx, out, cmd, file_type='sh', raw=True)

    @commands.command(hidden=True)
    async def load(self, ctx, *, module):
        """Loads a module."""
        # noinspection PyBroadException
        try:
            self.bot.load_extension(module)
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.auto_react()

    @commands.command(hidden=True)
    async def unload(self, ctx, *, module):
        """Unloads a module."""
        # noinspection PyBroadException
        try:
            self.bot.unload_extension(module)
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.auto_react()

    @commands.command(name='reload', hidden=True, aliases=['r'])
    async def _reload(self, ctx, *, module):
        """Reloads a module."""
        if not module.startswith('cogs.'):
            module = f'cogs.{module}'

        # noinspection PyBroadException
        try:
            self.bot.unload_extension(module)
            self.bot.load_extension(module)
        except Exception:
            await ctx.send(f'```py\n{traceback.format_exc()}\n```')
        else:
            await ctx.auto_react()

    @staticmethod
    def format_error(err):
        if not err.text:
            return f'```py\n{err.__class__.__name__}: {err}\n```'

        return f'```py\n{err.text}{"↑":>{err.offset}}\n{type(err).__name__}:' \
               f' {err}```'

    @commands.command(pass_context=True, hidden=True, name='eval')
    async def _eval(self, ctx, *, body: str):
        """Evaluates some code"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except SyntaxError as e:
            return await ctx.send(self.format_error(e))

        func = env['func']
        # noinspection PyBroadException
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            # noinspection PyBroadException
            try:
                await ctx.message.add_reaction('✅')
            except BaseException:
                pass

            await self.send_response(ctx, value, to_compile, extra=ret)

    @commands.command(pass_context=True, hidden=True)
    async def calc(self, ctx, *, body: str):
        """Evaluates some code with sympy imported"""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        body = body.splitlines()
        body[-1] = f'return {body[-1]}'
        body = '\n'.join(body)

        stdout = io.StringIO()

        to_compile = f'from sympy.abc import *\nfrom sympy import *\n' \
                     f'async def func():\n{textwrap.indent(body, "  ")}'

        # noinspection PyBroadException
        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        # noinspection PyBroadException
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            # noinspection PyBroadException
            try:
                await ctx.message.add_reaction('✅')
            except:
                pass

            await self.send_response(ctx, value, to_compile, extra=ret)

    @commands.command(pass_context=True, hidden=True)
    async def repl(self, ctx):
        """Launches an interactive REPL session."""
        variables = {
            'ctx': ctx,
            'bot': self.bot,
            'message': ctx.message,
            'guild': ctx.guild,
            'channel': ctx.channel,
            'author': ctx.author,
            '_': None,
        }

        if ctx.channel.id in self.sessions:
            await ctx.send(
                'Already running a REPL session in this channel.'
                ' Exit it with `quit`.'
            )
            return

        self.sessions.add(ctx.channel.id)
        await ctx.send(
            'Enter code to execute or evaluate. `exit()` or `quit` to exit.'
        )

        def check(m):
            return m.author.id == ctx.author.id and \
                   m.channel.id == ctx.channel.id and \
                   m.content.startswith('`')

        while True:
            try:
                response = await self.bot.wait_for('message', check=check,
                                                   timeout=10.0 * 60.0)
            except asyncio.TimeoutError:
                await ctx.send('Exiting REPL session.')
                self.sessions.remove(ctx.channel.id)
                break

            cleaned = self.cleanup_code(response.content)

            if cleaned in ('quit', 'exit', 'exit()', 'stop', 'stop()'):
                await ctx.send('Exiting.')
                self.sessions.remove(ctx.channel.id)
                return

            executor = exec
            if cleaned.count('\n') == 0:
                # single statement, potentially 'eval'
                try:
                    code = compile(cleaned, '<repl session>', 'eval')
                except SyntaxError:
                    pass
                else:
                    executor = eval

            if executor is exec:
                try:
                    code = compile(cleaned, '<repl session>', 'exec')
                except SyntaxError as e:
                    await ctx.send(self.get_syntax_error(e))
                    continue

            variables['message'] = response

            fmt = None
            stdout = io.StringIO()

            # noinspection PyBroadException
            try:
                with redirect_stdout(stdout):
                    # noinspection PyUnboundLocalVariable
                    result = executor(code, variables)
                    if inspect.isawaitable(result):
                        result = await result
            except Exception:
                value = stdout.getvalue()
                fmt = f'```py\n{value}{traceback.format_exc()}\n```'
            else:
                value = stdout.getvalue()
                if result is not None:
                    fmt = f'```py\n{value}{result}\n```'
                    variables['_'] = result
                elif value:
                    fmt = f'```py\n{value}\n```'

            try:
                if fmt is not None:
                    if len(fmt) > 2000:
                        await ctx.send('Content too big to be printed.')
                    else:
                        await ctx.send(fmt)
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                await ctx.send(f'Unexpected error: `{e}`')

    @commands.command(hidden=True)
    async def explode(self, ctx):
        await ctx.auto_react()
        await ctx.bot.logout()

    @commands.command(hidden=True)
    async def game(self, ctx, *, game: str = None):
        game = game if game else random.choice(self.bot.game_list)

        if game != 'NONE':
            await self.bot.change_presence(
                game=discord.Game(name=game)
            )
        else:
            await self.bot.change_presence(
                game=None
            )

        await ctx.auto_react()

    @commands.command(hidden=True)
    async def set_nick(self, ctx, *, nick: str):
        await ctx.guild.me.edit(nick=nick)
        await ctx.auto_react()

    # from
    # https://github.com/khazhyk/dango.py/blob/master/plugins/debug.py#L155-L166
    @commands.command(name="as", hidden=True)
    async def _as(self, ctx, who: commands.MemberConverter, *, cmd):
        """Run a command impersonating another user."""
        fake_msg = copy.copy(ctx.message)

        # noinspection PyProtectedMember
        fake_msg._update(
            ctx.message.channel,
            dict(
                content=ctx.prefix + cmd
            )
        )
        fake_msg.author = who

        new_ctx = await self.bot.get_context(fake_msg, cls=Context)

        async with new_ctx.acquire(new_ctx, None):
            await self.bot.invoke(new_ctx)


def setup(bot):
    bot.add_cog(Admin(bot))
