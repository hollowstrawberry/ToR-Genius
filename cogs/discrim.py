from collections import Counter

import discord
import numpy as np
from discord.ext import commands
from scipy import stats

from cogs.utils.paginator import EmbedPages


class Discrim:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def discriminfo(self, ctx):
        discrim_list = [int(u.discriminator) for u in ctx.guild.members]

        # The range is so we can get any discrims that no one has.
        # Just subtract one from the number of uses.
        count = Counter(discrim_list + [int(i) for i in range(1, 10000)])
        count = sorted(count.items(), key=lambda c: c[1], reverse=True)

        data = {
            'Most ': ', '.join(str(d[0]) for d in count[:5]) + ', and ' + str(count[6][0]),
            'least common': ', '.join(str(d[0]) for d in count[-4:-1][::-1]) + ', and' +
                            str(count[-1][0]),
            'mean': np.mean(discrim_list),
            'mode': stats.mode(discrim_list),
            'median': np.median(discrim_list),
            'Standard Deviation': np.std(discrim_list),
            'unused': '\n'.join([str(d) for d in count if d[1] == 1][:10])
        }

        embeds = {
            'Summary': {
                'Most Common': ', '.join(str(d[0]) for d in count[:3]) + ', and ' + str(count[4][0]),
                'Least Common': ', '.join(str(d[0]) for d in count[-4:-1][::-1] if d[1] != 1) + ', and ' + str(count[-1][0]),
                'Three Unused': '\n'.join([str(d[0]) for d in count if d[1] == 1][:3]),
                'Average': np.mean(discrim_list),
            },
            'Statistics': {
                'Average': np.mean(discrim_list),
                'Mode': stats.mode(discrim_list)[0][0],
                'Median': np.median(discrim_list),
                'Standard Deviation': np.std(discrim_list),
            }
        }
        #
        # e = discord.Embed(
        #     title="Embed Info",
        #     color=ctx.author.top_role.color
        # )
        #
        # for fieldName in data.keys():
        #     e.add_field(name=fieldName, value=data[fieldName])
        #
        # await ctx.send(embed=e)

        final_embeds = []

        for embed_title in embeds.keys():
            e = discord.Embed(title=embed_title)
            for field_name in embeds[embed_title].keys():
                e.add_field(name=field_name, value=embeds[embed_title][field_name], inline=False)
            final_embeds.append(e)

        p = EmbedPages(ctx, embeds=final_embeds)
        await p.paginate()

    @commands.command()
    async def tmp(self, ctx):
        embeds = [
            discord.Embed(title="foo bar"),
            discord.Embed(title="foo bar1"),
            discord.Embed(title="foo bar2"),
            discord.Embed(title="foo bar3"),
            discord.Embed(title="foo bar4")
        ]

        p = EmbedPages(ctx, embeds=embeds)
        await p.paginate()


def setup(bot):
    bot.add_cog(Discrim(bot))
