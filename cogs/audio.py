import discord
from discord.ext import commands
import asyncio
import threading
import youtube_dl
import os
from random import choice as rndchoice
from random import shuffle
from .utils.dataIO import fileIO
from .utils import checks
import glob
import re
import aiohttp
from bs4 import BeautifulSoup
import json

if not discord.opus.is_loaded():
    discord.opus.load_opus('libopus-0.dll')

youtube_dl_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': "mp3",
    'outtmpl': '%(id)s',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True,
    'outtmpl': "data/audio/cache/%(id)s"}

class Audio:
    """Music streaming."""

    def __init__(self, bot):
        self.bot = bot
        self.music_player = EmptyPlayer()
        self.settings = fileIO("data/audio/settings.json", "load")
        self.queue_mode = False
        self.queue = []
        self.playlist = []
        self.current = -1 #current track index in self.playlist
        self.downloader = {"DONE" : False, "TITLE" : False, "ID" : False, "URL" : False, "DURATION" : False, "DOWNLOADING" : False}
        self.skip_votes = []

        self.sing =  ["https://www.youtube.com/watch?v=zGTkAVsrfg8", "https://www.youtube.com/watch?v=cGMWL8cOeAU",
                     "https://www.youtube.com/watch?v=vFrjMq4aL-g", "https://www.youtube.com/watch?v=WROI5WYBU_A",
                     "https://www.youtube.com/watch?v=41tIUr_ex3g", "https://www.youtube.com/watch?v=f9O2Rjn1azc"]

    @commands.command(pass_context=True, no_pm=True)
    async def play(self, ctx, link : str):
        """Plays link
        """
        if self.downloader["DOWNLOADING"]:
            await self.bot.say("I'm already downloading a track.")
            return
        msg = ctx.message
        if await self.check_voice(msg.author, msg):
            if self.is_playlist_valid([link]): # reusing a function
                if await self.is_alone_or_admin(msg.author):
                    self.queue = []  
                    self.current = -1
                    self.playlist = [link]
                    self.music_player.stop()
                else:
                    self.playlist = []
                    self.current = -1
                    if not self.queue: await self.bot.say("The link has been put into queue.")
                    self.queue.append(link)
            else:
                await self.bot.say("That link is not allowed.")

    @commands.command(aliases=["title"])
    async def song(self):
        """Shows song title
        """
        if self.downloader["TITLE"] and "localtracks" not in self.downloader["TITLE"]:
            url = ""
            if self.downloader["URL"]: url = 'Link : "' + self.downloader["URL"] + '"'
            await self.bot.say(self.downloader["TITLE"] + "\n" + url)
        else:
            await self.bot.say("No title available.")

    @commands.command(name="playlist", pass_context=True, no_pm=True)
    async def _playlist(self, ctx, name : str): #some checks here
        """Plays saved playlist
        """
        await self.start_playlist(ctx, name, random=False)

    @commands.command(pass_context=True, no_pm=True)
    async def mix(self, ctx, name : str): #some checks here
        """Plays saved playlist (shuffled)
        """
        await self.start_playlist(ctx, name, random=True)

    async def start_playlist(self, ctx, name, random=None):
        if self.downloader["DOWNLOADING"]:
            await self.bot.say("I'm already downloading a track.")
            return
        msg = ctx.message
        name += ".txt"
        if await self.check_voice(msg.author, msg):
            if os.path.isfile("data/audio/playlists/" + name):
                self.queue = []
                self.current = -1
                self.playlist = fileIO("data/audio/playlists/" + name, "load")["playlist"]
                if random: shuffle(self.playlist)
                self.music_player.stop()

    @commands.command(pass_context=True, aliases=["next"], no_pm=True)
    async def skip(self, ctx):
        """Skips song
        """
        msg = ctx.message
        if self.music_player.is_playing():
            if await self.is_alone_or_admin(msg.author):
                self.music_player.stop()
            else:
                await self.vote_skip(msg)

    async def vote_skip(self, msg):
        v_channel = msg.server.me.voice_channel
        if msg.author.voice_channel.id == v_channel.id:
            if msg.author.id in self.skip_votes:
                await self.bot.say("You already voted.")
                return
            self.skip_votes.append(msg.author.id)
            if msg.server.me.id not in self.skip_votes: self.skip_votes.append(msg.server.me.id)
            current_users = []
            for m in v_channel.voice_members:
                current_users.append(m.id)

            clean_skip_votes = [] #Removes votes of people no longer in the channel
            for m_id in self.skip_votes:
                if m_id in current_users:
                    clean_skip_votes.append(m_id)
            self.skip_votes = clean_skip_votes

            votes_needed = int((len(current_users)-1) / 2)

            if len(self.skip_votes)-1 >= votes_needed: 
                self.music_player.stop()
                self.skip_votes = []
                return
            await self.bot.say("You voted to skip. Votes: [{0}/{1}]".format(str(len(self.skip_votes)-1), str(votes_needed)))


    @commands.command(pass_context=True, no_pm=True)
    async def local(self, ctx, name : str):
        """Plays a local playlist"""
        if self.downloader["DOWNLOADING"]:
            await self.bot.say("I'm already downloading a track.")
            return
        msg = ctx.message
        localplaylists = self.get_local_playlists()
        if localplaylists and ("data/audio/localtracks/" not in name and "\\" not in name):
            if name in localplaylists:
                files = []
                if glob.glob("data/audio/localtracks/" + name + "/*.mp3"):
                    files.extend(glob.glob("data/audio/localtracks/" + name + "/*.mp3"))
                if glob.glob("data/audio/localtracks/" + name + "/*.flac"):
                    files.extend(glob.glob("data/audio/localtracks/" + name + "/*.flac"))
                if await self.is_alone_or_admin(msg.author):
                    if await self.check_voice(msg.author, ctx.message):
                        self.queue = []
                        self.current = -1
                        self.playlist = files
                        self.music_player.stop()
                else:
                    await self.bot.say("I'm in queue mode. Controls are disabled if you're in a room with multiple people.")
            else:
                await self.bot.say("There is no local playlist with that name.")
        else:
            await self.bot.say(message.channel, "There are no valid playlists in the localtracks folder.")

    @commands.command(pass_context=True, no_pm=True)
    async def loop(self, ctx):
        """Loops single song
        """
        msg = ctx.message
        if self.music_player.is_playing():
            if await self.is_alone_or_admin(msg.author):
                self.current = -1
                self.playlist = [self.downloader["URL"]]
                await self.bot.say("I will play this song on repeat.")
            else:
                await self.bot.say("I'm in queue mode. Controls are disabled if you're in a room with multiple people.")

    @commands.command(pass_context=True, no_pm=True)
    async def shuffle(self, ctx):
        """Shuffle playlist
        """
        msg = ctx.message
        if self.music_player.is_playing():
            if await self.is_alone_or_admin(msg.author):
                if self.playlist:
                    shuffle(self.playlist)
                    await self.bot.say("The order of this playlist has been mixed")
            else:
                await self.bot.say("I'm in queue mode. Controls are disabled if you're in a room with multiple people.")

    @commands.command(pass_context=True, aliases=["previous"], no_pm=True) #TODO, PLAYLISTS
    async def prev(self, ctx):
        """Previous song
        """
        msg = ctx.message
        if self.music_player.is_playing() and self.playlist:
            if await self.is_alone_or_admin(msg.author):
                self.current -= 2
                if self.current == -1:
                    self.current = len(self.playlist) -3
                elif self.current == -2:
                    self.current = len(self.playlist) -2
                self.music_player.stop()



    @commands.command(pass_context=True, no_pm=True)
    async def stop(self, ctx):
        """Stops audio activity
        """
        msg = ctx.message
        if self.music_player.is_playing():
            if await self.is_alone_or_admin(msg.author):
                await self.close_audio()
            else:
                await self.bot.say("You can't stop music when there are other people in the channel! Vote to skip instead.")
        else:
            await self.close_audio()

    async def close_audio(self):
        self.queue = []
        self.playlist = []
        self.current = -1
        self.music_player.stop()
        await asyncio.sleep(1)
        await self.bot.voice.disconnect()

    @commands.command(name="queue", pass_context=True, no_pm=True) #check that author is in the same channel as the bot
    async def _queue(self, ctx, link : str):
        """Add link to queue
        """
        if await self.check_voice(ctx.message.author, ctx.message):
            if not self.playlist:
                self.queue.append(link)
                await self.bot.say("Link added to queue.")
            else:
                await self.bot.say("I'm already playing a playlist.")

    async def is_alone_or_admin(self, author): #Direct control. fix everything
        if not self.settings["QUEUE_MODE"]:
            return True
        elif author.id == checks.settings["OWNER"]:
            return True
        elif discord.utils.get(author.roles, name=checks.settings["ADMIN_ROLE"]) is not None:
            return True
        elif discord.utils.get(author.roles, name=checks.settings["MOD_ROLE"]) is not None:
            return True
        elif len(author.voice_channel.voice_members) in (1, 2):
            return True
        else:
            return False

    @commands.command(name="sing", pass_context=True, no_pm=True)
    async def _sing(self, ctx):
        """Makes Red sing"""
        if self.downloader["DOWNLOADING"]:
            await self.bot.say("I'm already downloading a track.")
            return
        msg = ctx.message
        if await self.check_voice(msg.author, msg):
            if not self.music_player.is_playing():
                    self.queue = []
                    await self.play_video(rndchoice(self.sing))
            else:
                if await self.is_alone_or_admin(msg.author):
                    self.queue = []
                    await self.play_video(rndchoice(self.sing))
                else:
                    await self.bot.say("I'm already playing music for someone else at the moment.")

    @commands.group(name="list", pass_context=True)
    async def _list(self, ctx):
        """Lists playlists"""
        if ctx.invoked_subcommand is None:
            await self.bot.say("Type help list for info.")

    @_list.command(name="playlist", pass_context=True)
    async def list_playlist(self, ctx):
        msg = "Available playlists: \n\n```"
        files = os.listdir("data/audio/playlists/")
        if files:
            for i, f in enumerate(files):
                if f.endswith(".txt"):
                    if i % 4 == 0 and i != 0:
                        msg = msg + f.replace(".txt", "") + "\n"
                    else:
                        msg = msg + f.replace(".txt", "") + "\t"
            msg += "```"
            await self.bot.send_message(ctx.message.author, msg)
        else:
            await self.bot.say("There are no playlists.")

    @_list.command(name="local", pass_context=True)
    async def list_local(self, ctx):
        msg = "Available local playlists: \n\n```"
        dirs = self.get_local_playlists()
        if dirs:
            for i, d in enumerate(dirs):
                if i % 4 == 0 and i != 0:
                    msg = msg + d + "\n"
                else:
                    msg = msg + d + "\t"
            msg += "```"
            await self.bot.send_message(ctx.message.author, msg)
        else:
            await self.bot.say("There are no local playlists.")

    @commands.group(pass_context=True)
    @checks.mod_or_permissions()
    async def audioset(self, ctx):
        """Changes audio module settings"""
        if ctx.invoked_subcommand is None:
            msg = "```"
            for k, v in self.settings.items():
                msg += str(k) + ": " + str(v) + "\n"
            msg += "\nType help audioset to see the list of commands.```"
            await self.bot.say(msg)

    @audioset.command(name="queue")
    async def queueset(self, status : str):
        """Enables/disables queue"""
        status = status.lower()
        if status == "on" or status == "true":
            self.settings["QUEUE_MODE"] = True
            await self.bot.say("Queue mode is now on.")
        elif status == "off" or status == "false": 
            self.settings["QUEUE_MODE"] = False
            await self.bot.say("Queue mode is now off.")
        else:
            await self.bot.say("Queue status can be either on or off.")
            return
        fileIO("data/audio/settings.json", "save", self.settings)

    @audioset.command()
    async def maxlength(self, length : int):
        """Maximum track length for requested links"""
        self.settings["MAX_LENGTH"] = length
        await self.bot.say("Maximum length is now " + str(length) + " seconds.")
        fileIO("data/audio/settings.json", "save", self.settings)

    @audioset.command()
    async def volume(self, level : float):
        """Sets the volume (0-1)"""
        if level >= 0 and level <= 1:
            self.settings["VOLUME"] = level
            await self.bot.say("Volume is now set at " + str(level) + ". It will take effect after the current track.")
            fileIO("data/audio/settings.json", "save", self.settings)
        else:
            await self.bot.say("Volume must be between 0 and 1. Example: 0.40")

    async def play_video(self, link):
        self.downloader = {"DONE" : False, "TITLE" : False, "ID" : False, "URL": False, "DURATION" : False, "DOWNLOADING" : False}
        if "https://" in link or "http://" in link:
            path = "data/audio/cache/"
            t = threading.Thread(target=self.get_video, args=(link,self,))
            t.start()
        else: #local
            path = ""
            self.downloader = {"DONE" : True, "TITLE" : link, "ID" : link, "URL": False, "DURATION" : False, "DOWNLOADING" : False}
        while not self.downloader["DONE"]:
            await asyncio.sleep(1)
        if self.downloader["ID"]:
            try:
                self.music_player.stop()
                self.music_player = self.bot.voice.create_ffmpeg_player(path + self.downloader["ID"], options='''-filter:a "volume={}"'''.format(self.settings["VOLUME"]))
                self.music_player.start()
                if path != "": await self.bot.change_status(discord.Game(name=self.downloader["TITLE"]))
            except discord.errors.ClientException:
                print("Error: I can't play music without ffmpeg. Install it.")
                self.downloader = {"DONE" : False, "TITLE" : False, "ID" : False, "URL": False, "DURATION" : False, "DOWNLOADING" : False}
                self.queue = []
                self.playlist = []
            except Exception as e:
                print(e)
        else:
            pass


    async def check_voice(self, author, message):
        if self.bot.is_voice_connected():
            v_channel = message.server.me.voice_channel
            if author.voice_channel == v_channel:
                return True
            elif len(v_channel.voice_members) == 1:
                if author.is_voice_connected():
                    if author.voice_channel.permissions_for(message.server.me).connect:
                        await self.bot.join_voice_channel(author.voice_channel)
                        return True
                    else:
                        await self.bot.say("I need permissions to join that voice channel.")
                        return False
                else:
                    await self.bot.say("You need to be in a voice channel.")
                    return False
            else:
                if not self.playlist and not self.queue:
                    return True
                else:
                    await self.bot.say("I'm already playing music for other people.")
                    return False
        elif author.voice_channel:
            if author.voice_channel.permissions_for(message.server.me).connect:
                await self.bot.join_voice_channel(author.voice_channel)
                return True
            else:
                await self.bot.say("I need permissions to join that voice channel.")
                return False
        else:
            await self.bot.say("You need to be in a voice channel.")
            return False

    async def queue_manager(self):
        while "Audio" in self.bot.cogs:
            if self.queue and not self.music_player.is_playing():
                new_link = self.queue[0]
                self.queue.pop(0)
                self.skip_votes = []
                await self.play_video(new_link)
            elif self.playlist and not self.music_player.is_playing():
                if not self.current == len(self.playlist)-1:
                    self.current += 1
                else:
                    self.current = 0
                new_link = self.playlist[self.current]
                self.skip_votes = []
                await self.play_video(new_link)
            await asyncio.sleep(1)

    def get_video(self, url, audio):
        try:
            self.downloader["DOWNLOADING"] = True
            yt = youtube_dl.YoutubeDL(youtube_dl_options)
            v = yt.extract_info(url, download=False)
            if v["duration"] > self.settings["MAX_LENGTH"]: raise MaximumLength("Track exceeded maximum length. See help audioset maxlength")
            if not os.path.isfile("data/audio/cache/" + v["id"]):
                v = yt.extract_info(url, download=True)
            audio.downloader = {"DONE" : True, "TITLE" : v["title"], "ID" : v["id"], "URL" : url, "DURATION" : v["duration"], "DOWNLOADING" : False} #Errors out here if invalid link
        except Exception as e:
            print(e) # TODO
            audio.downloader = {"DONE" : True, "TITLE" : False, "ID" : False, "URL" : False, "DOWNLOADING" : False}

    async def incoming_messages(self, msg): # Workaround, need to fix
        if msg.author.id != self.bot.user.id:
            
            if msg.channel.is_private and msg.attachments != []:
                await self.transfer_playlist(msg)
        if not msg.channel.is_private:
            if not self.playlist and not self.queue and not self.music_player.is_playing() and msg.server.me.game != None:
                await self.bot.change_status(None)

    def get_local_playlists(self):
        dirs = []
        files = os.listdir("data/audio/localtracks/")
        for f in files:
            if os.path.isdir("data/audio/localtracks/" + f) and " " not in f:
                if glob.glob("data/audio/localtracks/" + f + "/*.mp3") != []:
                    dirs.append(f)
                elif glob.glob("data/audio/localtracks/" + f + "/*.flac") != []:
                    dirs.append(f)
        if dirs != []:
            return dirs
        else:
            return False

    @commands.command(pass_context=True, no_pm=True)
    async def addplaylist(self, ctx, name : str, link : str): #CHANGE COMMAND NAME
        """Adds tracks from youtube playlist link"""
        if self.is_playlist_name_valid(name) and len(name) < 25 and self.is_playlist_link_valid(link):
            if fileIO("playlists/" + name + ".txt", "check"):
                await self.bot.say("`A playlist with that name already exists.`")
                return False
            links = await self.parse_yt_playlist(link)
            if links:
                data = { "author"  : ctx.message.author.id,
                         "playlist": links,
                         "link"    : link}
                fileIO("data/audio/playlists/" + name + ".txt", "save", data)
                await self.bot.say("Playlist added. Name: {}".format(name))
            else:
                await self.bot.say("Something went wrong. Either the link was incorrect or I was unable to retrieve the page.")
        else:
            await self.bot.say("Something is wrong with the playlist's link or its filename. Remember, the name must be with only numbers, letters and underscores. Link must be this format: https://www.youtube.com/playlist?list=PLe8jmEHFkvsaDOOWcREvkgFoj6MD0pXXX")

    async def transfer_playlist(self, message):
        msg = message.attachments[0]
        if msg["filename"].endswith(".txt"):
            if not fileIO("data/audio/playlists/" + msg["filename"], "check"): #returns false if file already exists
                r = await aiohttp.get(msg["url"])
                r = await r.text()
                data = r.replace("\r", "")
                data = data.split()
                if self.is_playlist_valid(data) and self.is_playlist_name_valid(msg["filename"].replace(".txt", "")):
                    data = { "author" : message.author.id,
                             "playlist": data,
                             "link"    : False}
                    fileIO("data/audio/playlists/" + msg["filename"], "save", data)
                    await self.bot.send_message(message.channel, "Playlist added. Name: {}".format(msg["filename"].replace(".txt", "")))
                else:
                    await self.bot.send_message(message.channel, "Something is wrong with the playlist or its filename.") # Add formatting info
            else:
                await self.bot.send_message(message.channel, "A playlist with that name already exists. Change the filename and resubmit it.")

    def is_playlist_valid(self, data):
        data = [y for y in data if y != ""] # removes all empty elements
        data = [y for y in data if y != "\n"]
        pattern = "|".join(fileIO("data/audio/accepted_links.json", "load"))
        for link in data:
            rr = re.search(pattern, link, re.I | re.U)
            if rr == None:
                return False
        return True

    def is_playlist_link_valid(self, link):
        pattern = "^https:\/\/www.youtube.com\/playlist\?list=(.[^:/]*)"
        rr = re.search(pattern, link, re.I | re.U)
        if not rr == None:
            return rr.group(1)
        else:
            return False

    def is_playlist_name_valid(self, name):
        for l in name:
            if l.isdigit() or l.isalpha() or l == "_":
                pass
            else:
                return False
        return True

    async def parse_yt_playlist(self, url):
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        try:
            page = await aiohttp.post(url, headers=headers)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            tags = soup.find_all("tr", class_="pl-video yt-uix-tile ")
            links = []

            for tag in tags:
                links.append("https://www.youtube.com/watch?v=" + tag['data-video-id'])
            if links != []:
                return links
            else:
                return False
        except:
            return False

class EmptyPlayer(): #dummy player
    def __init__(self):
        pass

    def stop(self):
        pass

    def is_playing(self):
        return False

class MaximumLength(Exception):
    def __init__(self, m):
        self.message = m
    def __str__(self):
        return self.message

def check_folders():
    folders = ("data/audio", "data/audio/cache", "data/audio/playlists", "data/audio/localtracks")
    for folder in folders:
        if not os.path.exists(folder):
            print("Creating " + folder + " folder...")
            os.makedirs(folder)

def check_files():
    
    settings = {"VOLUME" : 0.5, "MAX_LENGTH" : 3700, "QUEUE_MODE" : True}

    if not os.path.isfile("data/audio/settings.json"):
        print("Creating default audio settings.json...")
        fileIO("data/audio/settings.json", "save", settings)

    allowed = ["^(https:\/\/www\\.youtube\\.com\/watch\\?v=...........*)", "^(https:\/\/youtu.be\/...........*)",
              "^(https:\/\/youtube\\.com\/watch\\?v=...........*)", "^(https:\/\/soundcloud\\.com\/.*)"]
    
    if not os.path.isfile("data/audio/accepted_links.json"):
        print("Creating accepted_links.json...")
        fileIO("data/audio/accepted_links.json", "save", allowed)

def setup(bot):
    check_folders()
    check_files()
    loop = asyncio.get_event_loop()
    n = Audio(bot)
    loop.create_task(n.queue_manager())
    bot.add_listener(n.incoming_messages, "on_message")
    bot.add_cog(n)