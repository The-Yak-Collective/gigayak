#simple gig manager using sqlite3
#database has one table: gigs and that table has the following  fields:
#   gigid INTEGER PRIMARY KEY - number of gig entry in table
#   creatorid text - discord id of creator
#   contents text - the contenst of teh gig - no internal formatting. consider showagig
#   filled int - 0= unfilled 1= yes filled
#   createdat int - timestamp of when gig created
#   filledat int - timestamp of filling

#using same scheme, also support project bot, help wanted bot, agenda bot and newletter bot

#use GIGAYAK_DISCORD_KEY as an env variable - the key for discord bot. needs read/write permission to channels

from discord.ext import tasks, commands
import discord
import asyncio
import os
import time
import datetime
from dotenv import load_dotenv
import sqlite3  #consider , "check_same_thread = False" on sqlite.connect()

GIG_CHAN=810196195246211092
gig_chan=0
from discord_gigayak import *

conn=sqlite3.connect('/home/yak/robot/gigayak/gigdatabase.db') #the connection should be global. 

db_c = conn.cursor()


load_dotenv('/home/yak/.env')


@client.event #needed since it takes time to connect to discord
async def on_ready(): 
    global gig_chan
    print('We have logged in as {0.user}'.format(client),  client.guilds)
    checkon_database()
    gig_chan=client.guilds[0].get_channel(GIG_CHAN)
    await update_gigchannel()
    return


def allowed(x,y): #is x allowed to play with item created by y
#permissions - some activities can only be done by yakshaver, etc. or by person who initiated action
    if x==y: #same person. setting one to zero will force role check
        return True
    mid=client.guilds[0].get_member(message.author.id)
    r=[x.name for x in mid.roles]
    if 'yakshaver' in r or 'yakherder' in r: #for now, both roles are same permissions
        return True
    return False


@client.event 
async def on_message(message): 
    if message.author == client.user:
        return #ignore own messages to avoid loops
		
    dmtarget=await dmchan(message.author.id,message.channel) #build backchannel to user, so we do not answer in general channel

#three bots that manage general lists
#gigabot
    await try_bot("gig",message)
#wantedbot
    await try_bot("wanted",message)
#newsitem bot
    await try_bot("newsitem",message)
	
#agendabot - agenda per channel
    await try_chan_bot('agenda',message)
#agendabot - readinglist per channel
    await try_chan_bot('reading',message)
		
#projbot - vote on projects
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

    if message.content.startswith("$projset"): #hidden feature
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

    if message.content.startswith("$projnewtext"): #instead of exiting text
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
        conts=int(message.content.split(maxsplit=1)[1])
        db_c.execute('''UPDATE projects set filled=1, filledat= ? where pjid=? ''',(int(time.time()),conts))
        conn.commit()
        s='removed from project list: ' +str(conts)
        await splitsend(message.channel,s,False)
        return

#function which provides functionality for a per-channel list-based bot "w"
async def try_chan_bot(w,message):
    if message.content.startswith("${}test".format(w)):
        s='this is a test response from {}bot'.format(w)
        await splitsend(message.channel,s,False)
        return
		
    if message.content.startswith("${}list".format(w)):
        s='list of {} items in this channel:\n\n'.format(w)+perchanlist(message.channel.id,w)
        await splitsend(message.channel,s,False)
        return
		
    if message.content.startswith("${}all".format(w)): #hidden feature. for testing
        s='list of {} items in all channels:\n\n'.format(w)+perchanlistall()
        await splitsend(message.channel,s,False)
        return
		
    if message.content.startswith("${}help".format(w)):
        s='''
${0}help         this message
${0}list         list of {0} items
${0}add TEXT     adds text as a new item for {0} for THIS channel
${0}drop ID    marks id as taken off {0}
        '''. format(w)
        await splitsend(message.channel,s,True)
        return
    if message.content.startswith("${}add".format(w)):
        conts=message.content.split(maxsplit=1)[1]
        db_c.execute('''insert into {} values (NULL,?,?,?,?,?,?,?)'''.format(w),(str(message.author.id),conts,0,int(time.time()),0,message.channel.id,message.jump_url))
        conn.commit()
        s='new {} item id: '.format(w) +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        return
        
    if message.content.startswith("${}drop".format(w)):
        conts=int(message.content.split(maxsplit=1)[1]) #consider adding reason option here
        db_c.execute('''UPDATE {0} set filled=1, filledat= ? where {0}id=? '''.format(w),(int(time.time()),conts))
        conn.commit()
        s='removed from {}: '.format(w) +str(conts)
        await splitsend(message.channel,s,False)
        return


#function which provides functionality for a list-based bot "w"
async def try_bot(w,message):
    if message.content.startswith("${}test".format(w)):
        s='this is a test response from {}bot'.format(w)
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("${}list".format(w)):
        s='list of outstanding {}s:\n\n'.format(w)+"\n\n".join(thelist(w))
        await splitsend(message.channel,s,False)
        return
    if message.content.startswith("${}help".format(w)):
        s='''
${0}help          this message
${0}list          lists available {0}s
${0}add TEXT      adds text as a new {0} and returns a {0}id
${0}drop {0}ID [REASON]   marks {0}id as closed. give optional reason
        '''.format(w)
        await splitsend(message.channel,s,True)
        return
    if message.content.startswith("${}add".format(w)):
        conts=message.content.split(maxsplit=1)[1]
        db_c.execute('''insert into {}s values (NULL,?,?,?,?,?,?)'''.format(w),(str(message.author.id),conts,0,int(time.time()),0,""))
        conn.commit()
        s='new {} id: '.format(w) +str(db_c.lastrowid)
        await splitsend(message.channel,s,False)
        if message.content.startswith("$gig"):
            await update_gigchannel()#later make general, if others have channels...
        return
        
    if message.content.startswith("${}drop".format(w)):
        thetmp=message.content.split(maxsplit=2)
        conts=int(thetmp[1])
        reason="none given"
        if len(thetmp)>2:
            reason=thetmp[2]
        db_c.execute('''UPDATE {0}s set filled=1, filledat= ?, reason= ? where {0}id=? '''.format(w),(int(time.time()),conts,reason))
        conn.commit()
        s='marked as filled: ' +str(conts)+reason
        await splitsend(message.channel,s,False)
        if message.content.startswith("$gig"):
            await update_gigchannel()#later make general, if others have channels...
        return

def pjset(pid, field, value): #set any value. note execute cannot have ? type parameters, only values
    db_c.execute('''UPDATE projects set {}=? where pjid=? '''.format(field),(value,pid))
    conn.commit()

    return

async def delete_all_gig_messages(): #for now, only bot messages and only on gig_chan
    def is_me(m):
        return m.author == client.user
    deleted = await gig_chan.purge(limit=100, check=is_me)


async def update_gigchannel():#later make it for multipel channels
    await delete_all_gig_messages()
    listofgigs=thelist("gig")
    for e in listofgigs:
        embed=discord.Embed(color=0xd12323)
        tpos=e.index('**)')
        id=e[6:tpos]
        temp=e[tpos+4:] 
        embed.add_field(name=id, value=temp, inline=False)
        await gig_chan.send(embed=embed)
#series of functions which generate formatted lists from the DB

def thelist(w):
    q=[]
    rows=db_c.execute('select * from {}s where filled=0'.format(w)).fetchall()
    for row in rows:
        thestring='(id **{}**) From <@{}>:\n{}'.format(row[0],row[1],row[2])#was client.get_user(int(row[1])).name, but this way discord parses
        q.append(thestring)
    return q


def agendalist(x): #obselete
    q=''
    rows=db_c.execute('select * from agenda where filled=0 AND chan=?',(x,)).fetchall()
    for row in rows:
        thestring='(id **{}**) From <@{}>:\n{}'.format(row[0],row[1],row[2])
        q=q+thestring+'\n\n'
    return q

def perchanlist(x,w):
    q=''
    rows=db_c.execute('select * from {} where filled=0 AND chan=?'.format(w),(x,)).fetchall()
    for row in rows:
        thestring='(id **{}**) From <@{}>:\n{}'.format(row[0],row[1],row[2])
        q=q+thestring+'\n\n'
    return q

def agendalistall(): #obselete
    q=''
    rows=db_c.execute('select * from agenda where filled=0 ').fetchall()
    for row in rows:
        thestring='(id **{}**) chan:#{} From <@{}>:\n{}'.format(row[0],row[6], row[1],row[2])
        q=q+thestring+'\n\n'
    return q
def perchanlistall(w):
    q=''
    rows=db_c.execute('select * from {} where filled=0 '.format(w)).fetchall()
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
#check if table exists in DB. if not, create it
#this function is RIPE for automation, which would also be carried over to "on message"
    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='gigs' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE gigs (gigid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, reason text)''') 
        conn.commit()
        
    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='wanteds' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE wanteds (wantedid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, reason text)''') 
        conn.commit()

    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='newsitems' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE newsitems (newsitemid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, reason text)''') 
        conn.commit()

    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='agenda' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE agenda (agendaid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, chan int, mlink text)''') 
        conn.commit()

    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='reading' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE reading (readingid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, chan int, mlink text)''') 
        conn.commit()


    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='projects' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE projects (pjid INTEGER PRIMARY KEY, creatorid text, contents text, filled int, createdat int, filledat int, upvotes int, downvotes int, status text)''') #nonuniform id name
        conn.commit() 
        
    db_c.execute('''SELECT count(name) FROM sqlite_master WHERE type='table' AND name='votes' ''')
    if db_c.fetchone()[0]!=1:
        db_c.execute('''CREATE TABLE votes (vid INTEGER PRIMARY KEY, creatorid text, pid INTEGER, updown int, contents text, createdat int)''') #nonuniform id name
        conn.commit()

async def dmchan(t,c):
#create DM channel betwen bot and user
    print("at dmchan:",t)
    if  not client.get_user(t):
        return c #answer in same channel if no dm
    target=client.get_user(t).dm_channel
    if (not target): 
        print("need to create dm channel",flush=True)
        target=await client.get_user(t).create_dm()
    return target

async def splitsend(ch,st,codeformat):
#send messages within discord limit + optional code-type formatting
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
