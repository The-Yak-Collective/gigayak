#simple gig manager using sqlite3
#database has one table: gigs and that table has the following  fields:
#   gigid INTEGER PRIMARY KEY - number of gig entry in table
#   creatorid text - discord id of creator
#   contents text - the contenst of teh gig - no internal formatting. consider showagig
#   filled int - 0= unfilled 1= yes filled
#   createdat int - timestamp of when gig created
#   filledat int - timestamp of filling

from discord.ext import tasks, commands
import discord
import asyncio
import os
import time
import datetime
from dotenv import load_dotenv
import sqlite3  #consider , "check_same_thread = False" on sqlite.connect()

from discord_gigayak import *

conn=sqlite3.connect('gigdatabase.db') #the connection should be global. 
db_c = conn.cursor()


load_dotenv('/home/yak/.env')


@client.event
async def on_ready(): 
    print('We have logged in as {0.user}'.format(client),  client.guilds)
    checkon_database()
    return


@client.event
async def on_message(message): 
    if message.author == client.user:
        return
    if message.content.startswith("$gigtest"):
        s='this is a test response'
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("$giglist"):
        s='list of outstanding gigs:\n\n'+giglist()
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("$gighelp"):
        s='''
$gighelp         this message
$giglist         lists available gigs
$gigadd TEXT     adds text as a new gig and returns a gigid
$gigdrop GIGID   marks gigid as taken
        '''
        await splitsend(message.channel,s,True)
        return
    if message.content.startswith("$gigadd"):
        conts=message.content[8:]
        db_c.execute('''insert into gigs values (NULL,?,?,?,?,?)''',(str(message.author.id),conts,0,int(time.time()),0))
        conn.commit()
        s='new gig id: ' +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        return
        
    if message.content.startswith("$gigdrop"):
        conts=int(message.content[9:])
        db_c.execute('''UPDATE gigs set filled=1, filledat= ? where gigid=? ''',(int(time.time()),conts))
        conn.commit()
        s='marked as filled: ' +db_c.lastrowid
        await splitsend(message.channel,s,False)
        return
        
def giglist():
    q=''
    rows=db_c.execute('select * from gigs where filled=0').fetchall()
    for row in rows:
        thestring='(id **{}**) From <@{}>:\n{}'.format(row[0],row[1],row[2])#was client.get_user(int(row[1])).name, but this way discord parses
        q=q+thestring+'\n\n'
    return q

def checkon_database(): 

    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='gigs' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE gigs (gigid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int)''') 
        conn.commit()


async def splitsend(ch,st,codeformat):
    if len(st)<1900: #discord limit is 2k and we want some play)
        if codeformat:
            await ch.send('```'+st+'```')
        else:
            await ch.send(st)
    else:
        x=st.rfind('\n',0,2000)
        if codeformat:
            await ch.send('```'+st[0:x]+'```')
        else:
            await ch.send(st[0:x])
        await splitsend(ch,st[x+1:],codeformat)

discord_token=os.getenv('GIGAYAK_DISCORD_KEY')
client.run(discord_token) 
