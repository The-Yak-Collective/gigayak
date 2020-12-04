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

conn=sqlite3.connect('/home/yak/robot/gigayak/gigdatabase.db') #the connection should be global. 
db_c = conn.cursor()


load_dotenv('/home/yak/.env')


@client.event
async def on_ready(): 
    print('We have logged in as {0.user}'.format(client),  client.guilds)
    checkon_database()
    return

def allowed(x,y): #is x allowed to play with item created by y
    if x==y:
        return True
    mid=client.guilds[0].get_member(message.author.id)
    r=[x.name for x in mid.roles]
    if 'yakshaver' in r or 'yakherder' in r:
        return True
    return False


@client.event
async def on_message(message): 
    if message.author == client.user:
        return
    dmtarget=await dmchan(message.author.id)
#gigabot
    await try_bot("gig",message)
    await try_bot("wanted",message)

#agendabot
    if message.content.startswith("$agendatest"):
        s='this is a test response from agendabot'
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("$agendalist"):
        s='list of agenda items in this channel:\n\n'+agendalist(message.channel.id)
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("$agendaall"):
        s='list of agenda items in this channel:\n\n'+agendalistall()
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("$agendahelp"):
        s='''
$agendahelp         this message
$agendalist         list of open agenda items
$agendaadd TEXT     adds text as a new item for agenda for THIS channel
$agendadrop AGID    marks agid as taken off agenda
        '''
        await splitsend(message.channel,s,True)
        return
    if message.content.startswith("$agendaadd"):
        conts=message.content[11:]
        db_c.execute('''insert into agenda values (NULL,?,?,?,?,?,?)''',(str(message.author.id),conts,0,int(time.time()),0,message.channel.id))
        conn.commit()
        s='new agenda item id: ' +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        return
        
    if message.content.startswith("$agendadrop"):
        conts=int(message.content[12:])
        db_c.execute('''UPDATE agenda set filled=1, filledat= ? where agid=? ''',(int(time.time()),conts))
        conn.commit()
        s='removed from agenda: ' +db_c.lastrowid
        await splitsend(message.channel,s,False)
        return
#projbot
    if message.content.startswith("$projtest"):
        s='this is a test response from projbot'
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("$projlist"):
        s='list of open projects:\n\n'+projlist()
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("$projhelp"):
        s='''
$projhelp               this message
$projlist               list of open projects
$projadd TEXT           adds text as a new project. recommended format: short-name blurb roam-link
$projnewtext PJID TEXT  changes the text of PJID
$proj+ PJID TEXT        upvote this project; give a reason if you want
$proj- PJID TEXT        upvote this project; give a reason if you want
$projvotes PJID         lists all votes and reasons for project PJID
$projdrop PJID          marks PJID as taken off agenda

go to https://roamresearch.com/#/app/ArtOfGig/page/DJVbvHE2_ to see how to add a new project
        '''
#$projset PJID FIELD VALUE sets field to value in pjid
        await splitsend(message.channel,s,True)
        return
    if message.content.startswith("$projadd"):
        conts=message.content.split(maxsplit=1)[1]
        db_c.execute('''insert into projects values (NULL,?,?,?,?,?,?,?,?)''',(str(message.author.id),conts,0,int(time.time()),0,0,0,""))
        conn.commit()
        s='new project id: ' +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        return

    if message.content.startswith("$projset"):
        cmd=message.content.split(maxsplit=3)
        if len(cmd)<3:
            return
        if not allowed(message.author.id,0):
            splitsend(dmtarget,'no permission to do this',False)
            return
        pjset(cmd[1],cmd[2],cmd[3])
        s='set {}.{} to {}: '.format(pid,field,value)
        await splitsend(message.channel,s,False)
        return

    if message.content.startswith("$projnewtext"):
        cmd=message.content.split(maxsplit=2)
        if len(cmd)<3:
            return
        if not allowed(message.author.id,int(db_c.execute('''select creatorid from projects where pjid=?''',(cmd[1],)).fetchone()[0])):
            splitsend(dmtarget,'no permission to do this',False)
            return
        pjset(cmd[1],"contents",cmd[2])
        s='new text put in project: ' +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        return

    if message.content.startswith("$proj+"):
        cmd=message.content.split(maxsplit=2)
        if len(cmd)<2:
            return
        if len(cmd)==2:
            cmd.append("no reason given")
        val=int(db_c.execute('''select upvotes from projects where pjid=?''',(cmd[1],)).fetchone()[0])
        pjset(cmd[1],"upvotes",val+1)
        s='upvoted project: ' +cmd[1]
        await splitsend(message.channel,s,False)
        db_c.execute('''insert into votes values (NULL,?,?,?,?,?)''',(str(message.author.id),cmd[1],+1,cmd[2],int(time.time())))
        conn.commit()
        return
        
    if message.content.startswith("$proj-"):
        cmd=message.content.split(maxsplit=2)
        if len(cmd)<2:
            return
        if len(cmd)==2:
            cmd.append("no reason given")
        val=int(db_c.execute('''select downvotes from projects where pjid=?''',(cmd[1],)).fetchone()[0])
        pjset(cmd[1],"downvotes",val-1)
        s='downvoted project: ' +cmd[1]
        await splitsend(message.channel,s,False)
        db_c.execute('''insert into votes values (NULL,?,?,?,?,?)''',(str(message.author.id),cmd[1],-1,cmd[2],int(time.time())))
        conn.commit()
        return
        
    if message.content.startswith("$projvotes"):
        cmd=message.content.split(maxsplit=1)
        if len(cmd)<2:
            return
        s='votes for project {}'.format(cmd[1]) +votelist(cmd[1])
        await splitsend(message.channel,s,False)
        return

    if message.content.startswith("$projdrop"):
        conts=int(message.content[10:])
        db_c.execute('''UPDATE projects set filled=1, filledat= ? where agid=? ''',(int(time.time()),conts))
        conn.commit()
        s='removed from project list: ' +db_c.lastrowid
        await splitsend(message.channel,s,False)
        return

async def try_bot(w,message):
    if message.content.startswith("${}test".format(w)):
        s='this is a test response from {}bot'.format(w)
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("${}list".format(w)):
        s='list of outstanding {}s:\n\n'.format(w)+thelist(w)
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("${}help".format(w)):
        s='''
${0}help         this message
${0}list         lists available {0}s
${0}add TEXT     adds text as a new {0} and returns a {0}id
${0}drop {0}ID   marks {0}id as taken
        '''.format(w)
        await splitsend(message.channel,s,True)
        return
    if message.content.startswith("${}add".format(w)):
        conts=message.content.split(maxsplit=1)[1]
        db_c.execute('''insert into {}s values (NULL,?,?,?,?,?)'''.format(w),(str(message.author.id),conts,0,int(time.time()),0))
        conn.commit()
        s='new {} id: '.format(w) +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        return
        
    if message.content.startswith("${}drop".format(w)):
        conts=int(message.content(maxsplit=1)[1])
        db_c.execute('''UPDATE {0}s set filled=1, filledat= ? where {0}id=? '''.format(w),(int(time.time()),conts))
        conn.commit()
        s='marked as filled: ' +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        return

def pjset(pid, field, value):
    db_c.execute('''UPDATE projects set {}=? where pjid=? '''.format(field),(value,pid))
    conn.commit()

    return



def thelist(w):
    q=''
    rows=db_c.execute('select * from {}s where filled=0'.format(w)).fetchall()
    for row in rows:
        thestring='(id **{}**) From <@{}>:\n{}'.format(row[0],row[1],row[2])#was client.get_user(int(row[1])).name, but this way discord parses
        q=q+thestring+'\n\n'
    return q

def agendalist(x):
    q=''
    rows=db_c.execute('select * from agenda where filled=0 AND chan=?',(x,)).fetchall()
    for row in rows:
        thestring='(id **{}**) From <@{}>:\n{}'.format(row[0],row[1],row[2])
        q=q+thestring+'\n\n'
    return q

def agendalistall():
    q=''
    rows=db_c.execute('select * from agenda where filled=0 ').fetchall()
    for row in rows:
        thestring='(id **{}**) chan:#{} From <@{}>:\n{}'.format(row[0],row[6], row[1],row[2])
        q=q+thestring+'\n\n'
    return q

def projlist():
    q=''
    rows=db_c.execute('select * from projects where filled=0').fetchall()
    for row in rows:
        thestring='(project **{}**) From <@{}> up:{} down:{} status:{}\n{}'.format(row[0],row[1],row[6],row[7],row[8],row[2])
        q=q+thestring+'\n\n'
    return q

def votelist(x):
    q=''
    rows=db_c.execute('select * from votes where pid=?',(x,)).fetchall()
    for row in rows:
        thestring='{} by <@{}> reason: {}'.format(row[3],row[1],row[4])
        q=q+thestring+'\n\n'
    return q

def checkon_database(): 

    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='gigs' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE gigs (gigid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int)''') 
        conn.commit()
    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='wanteds' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE wanteds (wantedid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int)''') 
        conn.commit()

    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='agenda' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE agenda (agid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, chan int)''') 
        conn.commit()

    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='projects' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE projects (pjid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, upvotes int, downvotes int, status text)''') 
        conn.commit()
        
    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='votes' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE votes (vid INTEGER PRIMARY KEY, creatorid text, pid INTEGER, updown int, contents text, createdat int)''') 
        conn.commit()

async def dmchan(t):
    target=client.get_user(t).dm_channel
    if (not target): 
        print("need to create dm channel",flush=True)
        target=await client.get_user(t).create_dm()
    return target

async def splitsend(ch,st,codeformat):
    if len(st)<1900: #discord limit is 2k and we want some play)
        if codeformat:
            await ch.send('```'+st+'```')
        else:
            await ch.send(st)
    else:
        x=st.rfind('\n',0,1900)
        if codeformat:
            await ch.send('```'+st[0:x]+'```')
        else:
            await ch.send(st[0:x])
        await splitsend(ch,st[x+1:],codeformat)

discord_token=os.getenv('GIGAYAK_DISCORD_KEY')
client.run(discord_token) 
