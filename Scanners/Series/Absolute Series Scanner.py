# -*- coding: utf-8 -*-

###### library  ########################################################### Functions, Constants #####
import sys                                                           # getdefaultencoding, getfilesystemencoding, platform, argv
import os                                                            # path, listdir
import tempfile                                                      # NamedTemporaryFile
import time                                                          # strftime
import datetime                                                      # datetime
import re                                                            # match, compilef, sub
import fnmatch                                                       # translate
import logging, logging.handlers                                     # FileHandler, Formatter, getLogger, DEBUG | RotatingFileHandler
import inspect                                                       # getfile, currentframe
import ssl                                                           # SSLContext
import zipfile                                                       # ZipFile, namelist
import json                                                          # loads
from lxml import etree                                               # fromstring
try:                 from ssl import PROTOCOL_TLS    as SSL_PROTOCOL # Python >= 2.7.13 #ssl.PROTOCOL_TLSv1
except ImportError:  from ssl import PROTOCOL_SSLv23 as SSL_PROTOCOL # Python <  2.7.13
try:                 from urllib.request import urlopen, Request     # Python >= 3.0
except ImportError:  from urllib2        import urlopen, Request     # Python == 2.x

#Plex Libraries
import Media                                                         # Episode
import VideoFiles                                                    # Scan
import Stack                                                         # Scan

try:     import filebot #from https://github.com/filebot/plex-agents, needs the scanner from FileBot installed
except:  FileBot = {}
else:    FileBot = {'TheTVDB': 'tvdb', 'AniDB': 'anidb', 'TheMovieDB::TV': 'tsdb', 'movie': 'tmdb'}
	
### http://www.zytrax.com/tech/web/regex.htm  # http://regex101.com/#python
def com(string):  return re.compile(string)                 #RE Compile
def cic(string):  return re.compile(string, re.IGNORECASE)  #RE Compile Ignore Case

### Log variables, regex, skipped folders, words to remove, character maps ###
SetupDone              = False
Log                    = None
Handler                = None
PLEX_ROOT              = ""
PLEX_LIBRARY           = {}
PLEX_LIBRARY_URL       = "http://localhost:32400/library/sections/"  # Allow to get the library name to get a log per library https://support.plex.tv/hc/en-us/articles/204059436-Finding-your-account-token-X-Plex-Token
SSL_CONTEXT            = ssl.SSLContext(SSL_PROTOCOL)
HEADERS                = {'Content-type': 'application/json'}

SOURCE_IDS             = cic(r'\[((?P<source>(anidb(|[2-4])|tvdb(|[2-5])|tmdb|tsdb|imdb|youtube(|2)))-(?P<id>[^\[\]]*)|(?P<yt>(PL[^\[\]]{16}|PL[^\[\]]{32}|(UU|FL|LP|RD|UC|HC)[^\[\]]{22})))\]')
SOURCE_ID_FILES        = ["anidb.id", "anidb2.id", "anidb3.id", "anidb4.id", "tvdb.id", "tvdb2.id", "tvdb3.id", "tvdb4.id", "tvdb5.id", "tmdb.id", "tsdb.id", "imdb.id", "youtube.id", "youtube2.id"]
SOURCE_ID_OFFSET       = cic(r"(?P<id>\d{1,7})-(?P<season>s\d{1,3})?(?P<episode>e-?\d{1,3})?")
ASS_MAPPING_URL        = 'https://rawgit.com/ZeroQI/Absolute-Series-Scanner/master/tvdb4.mapping.xml'

ANIDB_HTTP_API_URL     = 'http://api.anidb.net:9001/httpapi?request=anime&client=hama&clientver=1&protover=1&aid='
ANIDB_SLEEP_MIN        = 6
AniDBBan               = False
ANIDB_TVDB_MAPPING     = 'https://raw.githubusercontent.com/Anime-Lists/anime-lists/master/anime-list-master.xml'
ANIDB_TVDB_MAPPING_MOD = 'https://rawgit.com/ZeroQI/Absolute-Series-Scanner/master/anime-list-corrections.xml'
ANIDB_TVDB_MAPPING_LOC = 'anime-list-custom.xml'  # Custom local correction for ScudLee mapping file url

TVDB_API1_URL          = 'http://thetvdb.com/api/A27AD9BE0DA63333/series/%s/all/en.xml'
TVDB_API2_LOGIN        = "https://api.thetvdb.com/login"
TVDB_API2_KEY          = "A27AD9BE0DA63333"
TVDB_API2_EPISODES     = 'https://api.thetvdb.com/series/{}/episodes?page={}'

FILTER_CHARS    = "\\/:*?<>|;"  #_.~                                                                                                                                             # Windows file naming limitations + "~;" as plex cut title at this for the agent
SEASON_RX       = [                                                                                                                                                              ### Seasons Folders
                    cic(r'^Specials'),                                                                                                                                           # Specials (season 0)
                    #cic(r'^(Season|Series|Book|Saison|Livre|Temporada|S)[ _\-\.]*(?P<season>\d{1,4})(.*)?'),                                                                    # Season / Series / Book / Saison / Livre / S
                    cic(r'^((?P<show>.*)[\._\-\— ]+)?(Season|Series|Book|Saison|Livre|Temporada|[Ss])[\._\—\- ]*?(?P<season>\d{1,4}).*?'),                                        # (title) S01
                    cic(r'^(?P<show>.*)?[\._\-\— ]*?Volume[\._\-\— ]*?(?P<season>(?=[MDCLXVI])M*D?C{0,4}L?X{0,4}V?I{0,4}).*?'),                                                  # (title) S01
                    #cic(r'^(?P<season>\d{1,2})$'),                                                                                                                              # ##
                    cic(r'^(Saga|(Story )?Ar[kc])')]                                                                                                                             # Last entry, folder name droped but files kept: Saga / Story Ar[kc] / Ar[kc]
SERIES_RX       = [                                                                                                                                                              ######### Series regex - "serie - xxx - title" ###
  cic(r'(^|(?P<show>.*?)[ _\.\-]*)(?P<season>\d{1,2})XE?(?P<ep>\d{1,3})(([_\-X]|[_\-]\d{1,2}X)(?P<ep2>\d{1,3}))?([ _\.\-]+(?P<title>.*))?$'),                                    #  0 # 1x01
  cic(r'(^|(?P<show>.*?)[ _\.\-]*)SE?(?P<season>\d{1,4})[ _\.\-]?EP?(?P<ep>\d{1,3})(([ _\.\-]|EP?|[ _\.\-]EP?)(?P<ep2>\d{1,3}))?[ _\.]*(?P<title>.*?)$'),                        #  1 # s01e01-02 | ep01-ep02 | e01-02 | s01-e01 | s01 e01'(^|(?P<show>.*?)[ _\.\-]+)(?P<ep>\d{1,3})[ _\.\-]?of[ _\.\-]?\d{1,3}([ _\.\-]+(?P<title>.*?))?$',                                                              #  2 # 01 of 08 (no stacking for this one ?)
  cic(r'^(?P<show>.*?)[ _\.]-[ _\.](EP?)?(?P<ep>\d{1,3})(-(?P<ep2>\d{1,3}))?(V\d)?[ _\.]*?(?P<title>.*)$'),                                                                      #  2 # Serie - xx - title.ext | ep01-ep02 | e01-02
  cic(r'^(?P<show>.*?)[ _\.]\[(?P<season>\d{1,2})\][ _\.]\[(?P<ep>\d{1,3})\][ _\.](?P<title>.*)$'),
  cic(r'^\[.*\]\[(?P<show>.*)\]\[(?P<ep>\d{1,3})\].*$'),
  cic(r'(^|(?P<show>.*)[ _\.\-]+)(?P<season>\d{1,2})ACV(?P<ep>\d{1,2})([ _\.]+(?P<title>.*)|$)') #20th Television production format (Futurama)
  ]
MOVIE_RX        = cic(r'(?P<show>.*) \((?P<year>\d{4})\)$')
DATE_RX         = [ #https://support.plex.tv/articles/200381053-naming-date-based-tv-shows/
                    cic(r'(?P<year>\d{4})\W+(?P<month>\d{2})\W+(?P<day>\d{2})(\D|$)'),   # 2009-02-10
                    cic(r'(?P<month>\d{2})\W+(?P<day>\d{2})\W+(?P<year>\d{4})(\D|$)')]       # 02-10-2009
ANIDB_RX        = [                                                                                                                                                              ###### AniDB Specials episode offset regex array
                    cic(r'(^|(?P<show>.*?)[ _\.\-]+)(S|SP|SPECIAL)[ _\.]?(?P<ep>\d{1,2})(-(?P<ep2>\d{1,3}))?(V\d)?[ _\.]?(?P<title>.*)$'),                                         #  0 # 001-099 Specials
                    cic(r'(^|(?P<show>.*?)[ _\.\-]+)(OP|NCOP|OPENING)[ _\.]?(?P<ep>\d{1,2}[a-z]?)?[ _\.]?(V\d)?([ _\.\-]+(?P<title>.*))?$'),                                     #  1 # 100-149 Openings
                    cic(r'(^|(?P<show>.*?)[ _\.\-]+)(ED|NCED|ENDING)[ _\.]?(?P<ep>\d{1,2}[a-z]?)?[ _\.]?(V\d)?([ _\.\-]+(?P<title>.*))?$'),                                      #  2 # 150-199 Endings
                    cic(r'(^|(?P<show>.*?)[ _\.\-]+)(TRAILER|PROMO|PV|T)[ _\.]?(?P<ep>\d{1,2})[ _\.]?(V\d)?([ _\.\-]+(?P<title>.*))?$'),                                         #  3 # 200-299 Trailer, Promo with a  number  '(^|(?P<show>.*?)[ _\.\-]+)((?<=E)P|PARODY|PARODIES?) ?(?P<ep>\d{1,2})? ?(v2|v3|v4|v5)?(?P<title>.*)$',                                                                        # 10 # 300-399 Parodies
                    cic(r'(^|(?P<show>.*?)[ _\.\-]+)(O|OTHERS?)(?P<ep>\d{1,2})[ _\.]?(V\d)?([ _\.\-]+(?P<title>.*))?$'),                                                         #  4 # 400-499 Others
                    cic(r'(^|(?P<show>.*?)[ _\.\-]+)(EP?[ _\.\-]?)?(?P<ep>\d{1,3})((-|-?EP?)(?P<ep2>\d{1,3})|)?[ _\.]?(V\d)?([ _\.\-]+(?P<title>.*))?$')]                        #  5 # E01 | E01-02| E01-E02 | E01E02                                                                                                                       # __ # look behind: (?<=S) < position < look forward: (?!S)
ANIDB_OFFSET    = [        0,       100,      150,       200,     400,         0,         0]                                                                                     ###### AniDB Specials episode offset value array
ANIDB_TYPE      = ['Special', 'Opening', 'Ending', 'Trailer', 'Other', 'Episode', 'Episode']                                                                                     ###### AniDB titles
COUNTER         = 500

# Uses re.match() so forces a '^'
IGNORE_DIRS_RX_RAW  = [ '@Recycle', r'\.@__thumb', r'lost\+found', r'\.AppleDouble', r'\$Recycle.Bin', 'System Volume Information', 'Temporary Items', 'Network Trash Folder',   ###### Ignored folders
                        '@eaDir', 'Extras', r'Samples?', 'bonus', r'.*bonus disc.*', r'trailers?', r'.*_UNPACK_.*', r'.*_FAILED_.*', r'_?Misc', '.xattr', 'audio', 'sub']        # source: Filters.py  removed '\..*',
IGNORE_DIRS_RX      = [cic(entry) for entry in IGNORE_DIRS_RX_RAW]
# Uses re.match() so forces a '^'
IGNORE_FILES_RX_RAW = [ r'[ _\.\-]?sample', r'-Recap\.', r'\._', 'OST', 'soundtrack']                                                                                            # Skipped files (samples, trailers)
IGNORE_FILES_RX     = [cic(entry) for entry in IGNORE_FILES_RX_RAW]

VIDEO_EXTS          = [ '3g2', '3gp', 'asf', 'asx', 'avc', 'avi', 'avs', 'bin', 'bivx', 'divx', 'dv', 'dvr-ms', 'evo', 'fli', 'flv', 'img', 'iso', 'm2t', 'm2ts', 'm2v',         #
                        'm4v', 'mkv', 'mov', 'mp4', 'mpeg', 'mpg', 'mts', 'nrg', 'nsv', 'nuv', 'ogm', 'ogv', 'tp', 'pva', 'qt', 'rm', 'rmvb', 'sdp', 'swf', 'svq3', 'strm',      #
                        'ts', 'ty', 'vdr', 'viv', 'vp3', 'wmv', 'wpl', 'wtv', 'xsp', 'xvid', 'webm', 'ifo', 'disc']                                                              # DVD: 'ifo', 'bup', 'vob'

WHACK_PRE_CLEAN_RAW = [ "x264-FMD Release", "x264-h65", "x264-mSD", "x264-BAJSKORV", "x264-MgB", "x264-SYS", "x264-FQM", "x264-ASAP", "x264-QCF", "x264-W4F", 'x264-w4f', "x264-AAC", 
                        'x264-2hd', "x264-ASAP", 'x264-bajskorv', 'x264-batv', "x264-BATV", "x264-EXCELLENCE", "x264-KILLERS", "x264-LOL", 'x264-MgB', 'x264-qcf', 'x264-SnowDoN', 'x264-xRed', 
                        "H.264-iT00NZ", "H.264.iT00NZ", 'H264-PublicHD', "H.264-BS", 'REAL.HDTV', "WEB.DL", "H_264_iT00NZ", "www.crazy-torrent.com", "ReourceRG Kids Release", "Paramount",
                        "By UniversalFreedom", "XviD-2HD", "XviD-AFG", "xvid-aldi", 'xvid-asap', "XviD-AXED", "XviD-BiA-mOt", 'xvid-fqm', "xvid-futv", 'xvid-killer', "XviD-LMAO", 'xvid-pfa',
                        'xvid-saints', "XviD-T00NG0D", "XViD-ViCKY", "XviD-BiA", "XVID-FHW", "PROPER-LOL", "5Banime-koi_5d", "%5banime-koi%5d", "minitheatre.org", "mthd bd dual", "WEB_DL",
                        "HDTV-AFG", "HDTV-LMAO", "ResourceRG Kids", "kris1986k_vs_htt91",   'web-dl', "-Pikanet128", "hdtv-lol", "REPACK-LOL", " - DDZ", "OAR XviD-BiA-mOt", "3xR", "(-Anf-)",
                        "Anxious-He", "Coalgirls", "Commie", "DarkDream", "Doremi", "ExiledDestiny", "Exiled-Destiny", "Exiled Destiny", "FFF", "FFFpeeps", "Hatsuyuki", "HorribleSubs", 
                        "joseole99", "(II Subs)", "OAR HDTV-BiA-mOt", "Shimeji", "(BD)", "(RS)", "Rizlim", "Subtidal", "Seto-Otaku", "OCZ", "_dn92__Coalgirls__", "CasStudio",
                        "(BD 1920x1080 Hi10P, JPN+ENG)", "(BD 1280x720 Hi10P)", "(DVD_480p)", "(1080p_10bit)", "(1080p_10bit_DualAudio)", "(Tri.Audio)", "(Dual.Audio)", "(BD_720p_AAC)", "x264-RedBlade",
                        "BD 1080p", "BD 960p", "BD 720p", "BD_720p", "TV 720p", "DVD 480p", "DVD 476p", "DVD 432p", "DVD 336p", "1080p.BluRay", "FLAC5.1", "x264-CTR", "1080p-Hi10p", "FLAC2.0",
                        "1920x1080", "1280x720", "848x480", "952x720", "(DVD 720x480 h264 AC3)", "(720p_10bit)", "(1080p_10bit)", "(1080p_10bit", "(BD.1080p.AAC)", "[720p]", "WEBDL", "NewStudio",
                        "H.264_AAC", "Hi10P", "Hi10", "x264", "BD 10-bit", "DXVA", "H.264", "(BD, 720p, FLAC)", "Blu-Ray", "Blu-ray",  "SD TV", "SD DVD", "HD TV",  "-dvdrip", "dvd-jap", "(DVD)", "BDRip",
                        "FLAC", "Dual Audio", "AC3", "AC3.5.1", "AC3-5.1", "AAC2.0", "AAC.2.0", "AAC2_0", "AAC", "1080p", 'DD2.1', 'DD5.1', "5.1",'divx5.1', "DD5_1", "TV-1", "TV-2", "TV-3", "TV-4", "TV-5",
                        "(Exiled_Destiny)", "720p", "480p", "_BD", ".XVID", "(xvid)", "dub.sub_ja+.ru+", "dub.sub_en.ja", "dub_en", "Rus", "Eng", "UNCENSORED", "THD", "H264", "2xDVO", "Subs", "Sub",
                        "-Cd 1", "-Cd 2", "Vol 1", "Vol 2", "Vol 3", "Vol 4", "Vol 5", "Vol.1", "Vol.2", "Vol.3", "Vol.4", "Vol.5",
                        "%28", "%29", " (1)", "(Clean)", "vostfr", "HEVC", "(Bonus inclus)", "(BD 1920x1080)", "10Bits-WKN", "WKN", "(Complet)", "Despair-Paradise", "Shanks@", "[720p]", "10Bits", 
                        "(TV)", "[DragonMax]", "INTEGRALE", "MKV", "MULTI", "DragonMax", "Zone-Telechargement.Ws", "Zone-Telechargement", "AniLibria.TV", "HDTV-RIP"
                      ]                                                                                                                                                               #include spaces, hyphens, dots, underscore, case insensitive
WHACK_PRE_CLEAN     = [cic(re.escape(entry)) for entry in WHACK_PRE_CLEAN_RAW]
WHACK               = [                                                                                                                                                               ### Tags to remove (lowercase) ###
                        'x264', 'h264', 'dvxa', 'divx', 'xvid', 'divx51', 'mp4', "avi", '8bit', '8-bit', 'hi10', 'hi10p', '10bit', '10-bit', 'crf24', 'crf 24', 'hevc',               # Video Codecs (color depth and encoding)
                        '480p', '576p', '720p', '1080p', '1080i',                                                                                                                     # Resolution
                        '24fps', '25fps', 'ntsc', 'pal', 'ntsc-u', 'ntsc-j',                                                                                                          # Refresh rate, Format
                        'mp3', 'ogg', 'ogm', 'vorbis', 'aac', 'dts', 'ac3', 'ac-3', '5.1ch', '5.1', '7.1ch',  'qaac',                                                                 # Audio Codecs, channels
                        'dc', 'se', 'extended', 'unrated', 'multi', 'multisubs', 'dubbed', 'dub', 'subbed', 'sub', 'engsub', 'eng', 'french', 'fr', 'jap', "JPN+ENG",                 # edition (dc = directors cut, se = special edition), subs and dubs
                        'custom', 'internal', 'repack', 'proper', 'rerip', "raw", "remastered", "uncensored", 'unc', 'cen',                                                           # format
                        'cd1', 'cd2', 'cd3', 'cd4', '1cd', '2cd', '3cd', '4cd', 'xxx', 'nfo', 'read.nfo', 'readnfo', 'nfofix', 'fragment', 'fs', 'ws', "- copy", "reenc", "hom",      # misc
                        'retail', 'webrip', 'web-dl', 'wp', 'workprint', "mkv",  "v1", "v2", "v3", "v4", "v5"                                                                         # release type: retail, web, work print
                        'bdrc', 'bdrip', 'bluray', 'bd', 'brrip', 'hdrip', 'hddvd', 'hddvdrip', 'wsrip',                                                                              # Source: bluray
                        'ddc', 'dvdrip', 'dvd', 'r1', 'r3', 'r5', "dvd", 'svcd', 'vcd', 'sd', 'hd', 'dvb', "release", 'ps3avchd',                                                     # Source: DVD, VCD, S-VCD
                        'dsr', 'dsrip', 'hdtv', 'pdtv', 'ppv', 'stv', 'tvrip', 'complete movie', "hiei", "metis", "norar",                                                            # Source: dtv, stv
                        'cam', 'bdscr', 'dvdscr', 'dvdscreener', 'scr', 'screener', 'tc', 'telecine', 'ts', 'telesync', 'mp4',                                                        # Source: screener
                        "mthd", "thora", 'sickrage', 'brrip', "remastered", "yify", "tsr", "reidy", "gerdhanse", 'remux',                                                             #'limited', 
                        'rikou', 'hom?', "it00nz", "nn92", "mthd", "elysium", "encodebyjosh", "krissy", "reidy", "it00nz", "s4a", "MVO", "VO"                                         # Release group
                      ]
               
# Word Search Compiled Regex (IGNORECASE is not required as word is lowered at start)
WS_VERSION          = com(r"v\d$")
WS_DIGIT            = com(r"^\d+(\.\d+)?$")
WS_MULTI_EP_SIMPLE  = com(r"^(?P<ep>\d{1,3})-(?P<ep2>\d{1,3})$")
WS_MULTI_EP_COMPLEX = com(r"^(ep?[ -]?)?(?P<ep>\d{1,3})(-|ep?|-ep?)(?P<ep2>\d{1,3})")
WS_SPECIALS         = com(r"^((t|o)\d{1,3}$|(sp|special|op|ncop|opening|ed|nced|ending|trailer|promo|pv|others?)(\d{1,3})?$)")
# Switch to turn on youtube date scanning
SW_YOUTUBE_DATE     = False

### Setup core variables ################################################################################
def setup():
  global SetupDone
  if SetupDone:  return
  else:          SetupDone = True
  
  ### Define PLEX_ROOT ##################################################################################
  global PLEX_ROOT
  PLEX_ROOT = os.path.abspath(os.path.join(os.path.dirname(inspect.getfile(inspect.currentframe())), "..", ".."))
  if not os.path.isdir(PLEX_ROOT):
    path_location = { 'Windows': '%LOCALAPPDATA%\\Plex Media Server',
                      'MacOSX':  '$HOME/Library/Application Support/Plex Media Server',
                      'Linux':   '$PLEX_HOME/Library/Application Support/Plex Media Server',
                      'Android': '/storage/emulated/0/Plex Media Server' }
    PLEX_ROOT = os.path.expandvars(path_location[Platform.OS.lower()] if Platform.OS.lower() in path_location else '~')  # Platform.OS:  Windows, MacOSX, or Linux
  
  ### Define logging setup ##############################################################################
  global Log
  Log = logging.getLogger('main')
  Log.setLevel(logging.DEBUG)
  set_logging()
  
  ### Populate PLEX_LIBRARY #############################################################################
  Log.info(u"".ljust(157, '='))
  Log.info(u"Plex scan start: {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")))
  try:
    library_xml = etree.fromstring(read_url(Request(PLEX_LIBRARY_URL, headers={"X-Plex-Token": os.environ['X_PLEX_TOKEN']})))
    for directory in library_xml.iterchildren('Directory'):
      for location in directory.iterchildren('Location'):
        PLEX_LIBRARY[location.get('path')] = {'title': directory.get('title'), 'scanner': directory.get("scanner"), 'agent': directory.get('agent')}
        Log.info(u'id: {:>2}, type: {:<6}, agent: {:<30}, scanner: {:<30}, library: {:<24}, path: {}'.format(directory.get("key"), directory.get('type'), directory.get("agent"), directory.get("scanner"), directory.get('title'), location.get("path")))
  except Exception as e:  Log.error("Exception: '%s', library_xml could not be loaded. X-Plex-Token file created?" % (e))
  Log.info(u"".ljust(157, '='))
  
### Read in a local file ################################################################################  
def read_file(local_file):
  file_content = ""
  try:
    with open(local_file, 'r') as file:  file_content = file.read()
    return file_content
  except Exception as e:  Log.error("Error reading file '%s', Exception: '%s'" % (local_file, e)); raise e

### Write a local file ##################################################################################
def write_file(local_file, file_content):
  try:
    with open(local_file, 'w') as file:  file.write(file_content)
  except Exception as e:  Log.error("Error writing file '%s', Exception: '%s'" % (local_file, e)); raise e

### Read in a url #######################################################################################
def read_url(url, data=None):
  url_content = ""
  try:
    if data is None:  url_content = urlopen(url, context=SSL_CONTEXT).read()
    else:             url_content = urlopen(url, context=SSL_CONTEXT, data=data).read()
    return url_content
  except Exception as e:  Log.error("Error reading url '%s', Exception: '%s'" % (url, e)); raise e

### Download a url into the environment temp directory ##################################################
def read_cached_url(url, foldername='', filename='', cache=518400):  # cache=6days in seconds
  local_filename, hama_folder, file_content, file_content_cache, file_age = "", "", "", "", cache+1
  if not filename:  filename = os.path.basename(url)
  # Determine if files should be stored in the HAMA/DataItems folders or in the Temp directory
  if foldername:  hama_folder = os.path.join(PLEX_ROOT, 'Plug-in Support', 'Data', 'com.plexapp.agents.hama', 'DataItems')
  if foldername and os.path.exists(hama_folder):
    hama_folder = os.path.join(hama_folder, foldername)
    if not os.path.exists(hama_folder):  os.makedirs(hama_folder)
    local_filename = os.path.join(hama_folder, filename)
  else:
    local_filename = os.path.join(tempfile.gettempdir(), "ASS-" + (foldername.replace(os.path.sep, '-') + '-' if foldername else '') + filename)
  # Load the cached file's contents
  if os.path.exists(local_filename):
    file_content_cache = read_file(local_filename)
    file_age           = time.time() - os.path.getmtime(local_filename)
  try:
    # Check cached file's anime enddate and adjust cache age (same as HAMA)
    if "api.anidb.net" in url and file_content_cache:
      xml = etree.fromstring(file_content_cache)
      ed = (xml.xpath('enddate')[0].text if xml.xpath('enddate') else '') or datetime.datetime.now().strftime("%Y-%m-%d")
      enddate = datetime.datetime.strptime("{}-12-31".format(ed) if len(ed)==4 else "{}-{}".format(ed, ([30, 31] if int(ed[-2:])<=7 else [31, 30])[int(ed[-2:]) % 2] if ed[-2:]!='02' else 28) if len(ed)==7 else ed, '%Y-%m-%d')
      days_old = (datetime.datetime.now() - enddate).days
      if   days_old > 1825:  cache = 365*24*60*60                  # enddate > 5 years ago => 1 year cache
      elif days_old >   30:  cache = (days_old*365*24*60*60)/1825  # enddate > 30 days ago => (days_old/5yrs ended = x/1yrs cache)
    # Return the cached file string if it exists and is not too old
    if file_content_cache and file_age <= cache:
      Log.info(u"Using cached file - Filename: '{file}', Age: '{age:.2f} days', Limit: '{limit} days', url: '{url}'".format(file=local_filename, age=file_age/86400, limit=cache/86400, url=url))
      return file_content_cache
    # Pull the content down as either cache does not exist or is too old
    if "api.anidb.net" in url:
      global AniDBBan
      if AniDBBan:  # If a ban has been hit in scan run's life, return cached content (or nothing if there is no cached content)
        Log.info(u"Using cached file (AniDBBan) - Filename: '{file}', Age: '{age:.2f} days', Limit: '{limit} days', url: '{url}'".format(file=local_filename, age=file_age/86400, limit=cache/86400, url=url))
        return file_content_cache
      import StringIO, gzip
      file_content = gzip.GzipFile(fileobj=StringIO.StringIO(read_url(url))).read()
      time.sleep(ANIDB_SLEEP_MIN)
      if len(file_content)<512:  # Check if the content is too short and thus an error response
        if 'banned' in file_content:  AniDBBan = True
        Log.info(u"Using {action} file - Filename: '{file}', Age: '{age:.2f} days', Limit: '{limit} days', url: '{url}'".format(action="cached file" if file_content_cache else "error response", file=local_filename, age=file_age/86400, limit=cache/86400, url=url))
        Log.info(u"-- Error response received: {}".format(file_content))
        return file_content_cache or file_content  # If an error has been hit, return cached content (or error response if there is no cached content)
    elif "api.thetvdb.com" in url:
      if 'Authorization' in HEADERS:  Log.info(u'Authorised, HEADERS: {}'.format(HEADERS))
      else:
        page = read_url(Request(TVDB_API2_LOGIN, headers=HEADERS), data=json.dumps({"apikey": TVDB_API2_KEY}))
        HEADERS['Authorization'] = 'Bearer ' + json.loads(page)['token']
        Log.info(u'Now authorised, HEADERS: {}'.format(HEADERS))
      file_content = read_url(Request(url, headers=HEADERS))
    else:
      file_content = read_url(url)
    # Content was pulled down so save it
    if file_content:
      Log.info(u"{action} cached file - Filename: '{file}', Age: '{age:.2f} days', Limit: '{limit} days', url: '{url}'".format(action="Updating" if os.path.exists(local_filename) else "Creating", file=local_filename, age=file_age/86400, limit=cache/86400, url=url))
      write_file(local_filename, file_content)
    return file_content
  except Exception as e:  # Exception hit from possible: xml parsing, file reading/writing, bad url call
    Log.error("Error downloading '{}', Exception: '{}'".format(url, e))
    raise e

### Sanitize string #####################################################################################
def os_filename_clean_string(string):
  for char, subst in zip(list(FILTER_CHARS), [" " for x in range(len(FILTER_CHARS))]) + [("`", "'"), ('"', "'")]:    # remove leftover parenthesis (work with code a bit above)
    if char in string:  string = string.replace(char, subst)                                                         # translate anidb apostrophes into normal ones #s = s.replace('&', 'and')
  return string

#########################################################################################################  
def Dict(var, *arg, **kwarg):
  """ Return the value of an (imbricated) dictionnary, if all fields exist else return "" unless "default=new_value" specified as end argument
      Ex: Dict(variable_dict, 'field1', 'field2', default = 0)
  """
  for key in arg:
    if isinstance(var, dict) and key and key in var:  var = var[key]
    else:  return kwarg['default'] if kwarg and 'default' in kwarg else ""   # Allow Dict(var, tvdbid).isdigit() for example
  return kwarg['default'] if var in (None, '', 'N/A', 'null') and kwarg and 'default' in kwarg else "" if var in (None, '', 'N/A', 'null') else var

### Set Logging to proper logging file ##################################################################
def set_logging(root='', foldername='', filename='', backup_count=0, format='%(message)s', mode='a'):#%(asctime)-15s %(levelname)s - 
  if Dict(PLEX_LIBRARY, root, 'agent') == 'com.plexapp.agents.hama':  cache_path = os.path.join(PLEX_ROOT, 'Plug-in Support', 'Data', 'com.plexapp.agents.hama', 'DataItems', '_Logs')
  else:                                                               cache_path = os.path.join(PLEX_ROOT, 'Logs', 'ASS Scanner Logs')

  if not foldername:                  foldername = Dict(PLEX_LIBRARY, root, 'title')  # If foldername is not defined, try and pull the library title from PLEX_LIBRARY
  if foldername:                      cache_path = os.path.join(cache_path, os_filename_clean_string(foldername))
  if not os.path.exists(cache_path):  os.makedirs(cache_path)
  
  filename = os_filename_clean_string(filename) if filename else '_root_.scanner.log'
  log_file = os.path.join(cache_path, filename)
  
  # Bypass DOS path MAX_PATH limitation (260 Bytes=> 32760 Bytes, 255 Bytes per folder unless UDF 127B ytes max)
  if os.sep=="\\":
    dos_path = os.path.abspath(log_file) if isinstance(log_file, unicode) else os.path.abspath(log_file.decode('utf-8'))
    log_file = u"\\\\?\\UNC\\" + dos_path[2:] if dos_path.startswith(u"\\\\") else u"\\\\?\\" + dos_path

  #if not mode:  mode = 'a' if os.path.exists(log_file) and os.stat(log_file).st_mtime + 3600 > time.time() else 'w' # Override mode for repeat manual scans or immediate rescans

  global Handler
  if Handler:       Log.removeHandler(Handler)
  if backup_count:  Handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=backup_count, encoding='utf-8')
  else:             Handler = logging.FileHandler                 (log_file, mode=mode, encoding='utf-8')
  Handler.setFormatter(logging.Formatter(format))
  Handler.setLevel(logging.DEBUG)
  Log.addHandler(Handler)

### Turn a string into a list of string and number chunks  "z23a" -> ["z", 23, "a"] #####################
def natural_sort_key(s, _nsre=com(r'(\d+)')):  return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]

def filter_chars(string):
  for char, subst in zip(list(FILTER_CHARS), [" " for x in range(len(FILTER_CHARS))]):
    if char in string:  string = string.replace(char, subst)
  return string

### Allow to display ints even if equal to None at times ################################################
CS_PARENTHESIS     = com(r"\([^\(\)]*?\)")
CS_BRACKETS_CHAR   = com(r"(\[|\]|\{|\})")
CS_BRACKETS        = com(r'(\[(?!\d{1,3}\])[^\[\]]*?\]|\{(?!\d{1,3}\})[^\{\}]*?\})')
CS_SPECIAL_EP_PAT, CS_SPECIAL_EP_REP   = com(r'(?P<a>[^0-9Ssv]\d{1,3})\.(?P<b>\d{1,2}(\D|$))'), r'\g<a>DoNoTfIlTeR\g<b>'
CS_CRC_HEX         = com(r"[0-9a-fA-F]{8}")
CS_VIDEO_SIZE      = com(r"\d{3,4} ?[Xx] ?\d{3,4}")
CS_PAREN_SPACE_PAT, CS_PAREN_SPACE_REP = com(r'\([ _\.]*(?P<internal>[^\(\)]*?)[ _\.]*\)'), r'(\g<internal>)'
CS_PAREN_EMPTY     = com(r'\([-Xx]?\)')

def clean_string(string, no_parenthesis=False, no_whack=False, no_dash=False, no_underscore=False, no_dot=False):
  if not string: return ""                                                                                                           # if empty return empty string
  if no_parenthesis:                                                                                                                 # delete parts between parenthesis if needed
    while CS_PARENTHESIS.search(string):            string = CS_PARENTHESIS.sub(' ', string)                                         # support imbricated parrenthesis like: "Cyborg 009 - The Cyborg Soldier ((Cyborg) 009 (2001))"
  while CS_BRACKETS.search(string):                 string = CS_BRACKETS.sub(' ', string)                                            # remove "[xxx]" groups but ep numbers inside brackets as Plex cleanup keep inside () but not inside [] #look behind: (?<=S) < position < look forward: (?!S)
  string = CS_BRACKETS_CHAR.sub("", string)                                                                                          # remove any remaining '{}[]' characters
  if not no_whack:
    for index, word in enumerate(WHACK_PRE_CLEAN):  string = word.sub(" ", string, 1) if WHACK_PRE_CLEAN_RAW[index].lower() in string.lower() else string  # Remove words present in pre-clean list
  string = CS_SPECIAL_EP_PAT.sub(CS_SPECIAL_EP_REP, string)                                                                          # Used to create a non-filterable special ep number (EX: 13.5 -> 13DoNoTfIlTeR5) # Restricvted to max 999.99 # Does not start with a season/special char 'S|s' (s2.03) or a version char 'v' (v1.2)
  string = filter_chars(string)
  for char, subst in [("`", "'"), ("(", " ( "), (")", " ) ")]:                                                                       # remove leftover parenthesis (work with code a bit above)
    if char in string:                              string = string.replace(char, subst)                                             # translate anidb apostrophes into normal ones #s = s.replace('&', 'and')
  string = string.replace("DoNoTfIlTeR", '.')                                                                                        # Replace 13DoNoTfIlTeR5 into 13.5 back
  string = CS_CRC_HEX.sub(' ', string)                                                                                               # CRCs removal
  string = CS_VIDEO_SIZE.sub(' ', string)                                                                                            # Video size ratio removal
  if string.rstrip().endswith(", The"):             string = "The " + ''.join( string.split(", The", 1) )                            # ", The" is rellocated in front
  if string.rstrip().endswith(", A"  ):             string = "A "   + ''.join( string.split(", A"  , 1) )                            # ", A"   is rellocated in front
  if not no_whack:                                  string = " ".join([word for word in filter(None, string.split()) if word.lower() not in WHACK]).strip()  # remove double spaces + words present in "WHACK" list #filter(None, string.split())
  if no_dash:                                       string = string.replace("-", " ")                                                # replace the dash '-'
  if no_dot:                                        string = string.replace(".", " ")                                                # replace the dash '-'
  if no_underscore:                                 string = string.replace("_", " ")                                                # replace the underscore '_'
  string = CS_PAREN_EMPTY.sub('', CS_PAREN_SPACE_PAT.sub(CS_PAREN_SPACE_REP, string))                                                # Remove internal spaces in parenthesis then remove empty parenthesis
  string = " ".join([word for word in filter(None, string.split())]).strip(" _.-")                                                   # remove multiple spaces and cleanup the ends
  for rx in ("-"):                                  string = string[len(rx):   ].strip() if string.startswith(rx)       else string  # In python 2.2.3: string = string.strip(string, " -_") #if string.startswith(("-")): string=string[1:]
  for rx in ("-", "- copy"):                        string = string[ :-len(rx) ].strip() if string.lower().endswith(rx) else string  # In python 2.2.3: string = string.strip(string, " -_")
  return string

### Add files into Plex database ########################################################################
def add_episode_into_plex(media, file, root, path, show, season=1, ep=1, title="", year=None, ep2="", rx="", tvdb_mapping={}, unknown_series_length=False, offset_season=0, offset_episode=0, mappingList={}):
  global COUNTER 
  if isinstance(show,  unicode):  ushow = show;  show  =  show.encode('utf-8')  #Plex expect Show in UTF-8
  else:                           ushow =  show.decode('utf-8')
  
  if title==title.lower() or title==title.upper() and title.count(" ")>0: title           = title.title()        # capitalise if all caps or all lowercase and one space at least
  if isinstance(title, unicode):  utitle= title; title = title.encode('utf-8')  #Plex expect Title in UTF-8
  else:                           utitle= title.decode('utf-8')
  
  if not os.path.exists(file):  file = os.path.join(root, path, file)
  if isinstance(file,  unicode):  ufile = os.path.basename(file);   file = file.encode(sys.getfilesystemencoding())
  else:                           ufile = os.path.basename(file.decode('utf-8'))
  
  # Season/Episode Offset
  if season > 0:  season, ep, ep2 = season+offset_season if offset_season >= 0 else 0, ep+offset_episode, ep2+offset_episode if ep2 else None
  
  # Mapping List 
  ep_orig        = "s{}e{}{}".format(season, ep, "" if not ep2 or ep==ep2 else "-{}".format(ep2))
  ep_orig_single = "s{}e{}".format  (season, ep)
  ep_orig_padded = "s{:>02d}e{:>03d}{}".format(int(season), int(ep), "    " if not ep2 or ep==ep2 else "-{:>03d}".format(int(ep2)))
  if ep_orig_single in mappingList:
    multi_ep   = 0 if ep_orig == ep_orig_single else ep2-ep
    season, ep = mappingList[ep_orig_single][1:].split("e"); season = int(season)
    if '-' in ep or  '+' in ep:  ep, ep2 = re.split("[-+]", ep, 1); ep, ep2 = int(ep), int(ep2) if ep2 and ep2.isdigit() else None
    else:                        ep, ep2 = int(ep), int(ep)+multi_ep if multi_ep else None
  elif season > 0:
    if Dict(mappingList, 'episodeoffset'):  ep, ep2 = ep+int(Dict(mappingList, 'episodeoffset')), ep2+int(Dict(mappingList, 'episodeoffset')) if ep2 else None 
    if Dict(mappingList, 'defaulttvdbseason') and not Dict(mappingList, 'defaulttvdbseason_a', default=False):  season = int(Dict(mappingList, 'defaulttvdbseason'))
  if ep<=0 and season == 0:                          COUNTER = COUNTER+1; season, ep, ep2 = 0, COUNTER, COUNTER  # s00e00    => s00e5XX (happens when ScudLee mapps to S0E0)
  if ep<=0 and season > 0:                                                season, ep, ep2 = 0, 1, 1              # s[1-0]e00 => s00e01
  if not ep2 or ep > ep2:                                                 ep2             = ep                   #  make ep2 same as ep for loop and tests
  if tvdb_mapping and season > 0 :
    max_ep_num, season_buffer = max(tvdb_mapping.keys()), 0 if unknown_series_length else 1
    if   ep  in tvdb_mapping:               season, ep  = tvdb_mapping[ep ]
    elif ep  > max_ep_num and season == 1:  season      = tvdb_mapping[max_ep_num][0]+season_buffer
    if   ep2 in tvdb_mapping:               season, ep2 = tvdb_mapping[ep2]
    elif ep2 > max_ep_num and season == 1:  season      = tvdb_mapping[max_ep_num][0]+season_buffer
  ep_final = "s%de%d" % (season, ep)
  
  for epn in range(ep, ep2+1):
    if len(show) == 0: Log.warning("show: '%s', s%02de%03d-%03d, file: '%s' has show empty, report logs to dev ASAP" % (show, season, ep, ep2, file))
    else:# Media.Episode expects show and title in utf-8 encoded byte string (unicode title in Plex Media Scanner/log': WARN - Warning, Unicode passed in, should be UTF-8 string for attribute 'name')
      tv_show = Media.Episode(show, season, epn, title, year)  #tv_show = Media.Episode(show.encode('utf-8'), season, epn, title.encode('utf-8'), year)
      tv_show.display_offset = (epn-ep)*100/(ep2-ep+1)
      if ufile.upper()==u"VIDEO_TS.IFO":  
        for item in os.listdir(os.path.dirname(file)) if os.path.dirname(file) else []:
          if item.upper().startswith("VTS_01_") and not item.upper()=="VTS_01_2.VOB":  tv_show.parts.append(os.path.join(os.path.dirname(file), item).encode(sys.getfilesystemencoding()))
      else:  tv_show.parts.append(file)  #.encode(sys.getfilesystemencoding()) gives UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2 in position 101: ordinal not in range(128)
      media.append(tv_show)   # at this level otherwise only one episode per multi-episode is showing despite log below correct
  index  = "SERIES_RX-"+str(SERIES_RX.index(rx)) if rx in SERIES_RX else "ANIDB_RX-"+str(ANIDB_RX.index(rx)) if rx in ANIDB_RX else rx  # rank of the regex used from 0
  multi  = '    ' if not ep2 or ep==ep2 else '-{:>03d}'.format(ep2)
  before = " (Orig: %s)" % ep_orig_padded if ep_orig!=ep_final else "".ljust(20, ' ')
  Log.info(u'"{show}" s{season:>02d}e{episode:>03d}{multi:s}{before} "{regex}" "{title}" "{file}"'.format(show=ushow, season=season, episode=ep, multi=multi, before=before, regex=index or '__', title=utitle, file=ufile))

### Get the tvdbId from the AnimeId #####################################################################
def anidbTvdbMapping(AniDB_TVDB_mapping_tree, anidbid):
  mappingList = {}
  for anime in AniDB_TVDB_mapping_tree.iter('anime') if AniDB_TVDB_mapping_tree is not None else []:
    if anime.get("anidbid") == anidbid and anime.get('tvdbid').isdigit():
      mappingList['episodeoffset']     = anime.get('episodeoffset')     or '0'  # Either entry is missing or exists but is blank
      mappingList['defaulttvdbseason'] = anime.get('defaulttvdbseason') or '1'  # Either entry is missing or exists but is blank
      if mappingList['defaulttvdbseason'] == 'a':  mappingList['defaulttvdbseason_a'] = True; mappingList['defaulttvdbseason'] = '1'
      else:                                        mappingList['defaulttvdbseason_a'] = False
      try:
        for season in anime.iter('mapping'):
          for episode in range(int(season.get("start")), int(season.get("end"))+1) if season.get("offset") else []:
            mappingList[ 's'+season.get("anidbseason") + 'e' + str(episode)          ] = 's' + season.get("tvdbseason") + 'e' + str(episode+int(season.get("offset")))
          for episode in filter(None, season.text.split(';')) if season.text else []:
            mappingList[ 's'+season.get("anidbseason") + 'e' + episode.split('-')[0] ] = 's' + season.get("tvdbseason") + 'e' + episode.split('-')[1] 
      except Exception as e: Log.error("mappingList creation exception: {}, mappingList: {}".format(e, mappingList))
      else:   Log.info(u"anidb: '%s', tvbdid: '%s', name: '%s', mappingList: %s" % (anidbid, anime.get('tvdbid'), anime.xpath("name")[0].text, str(mappingList)) )
      return anime.get('tvdbid'), mappingList
  Log.error("-- No valid tvbdbid found for anidbid '%s'" % (anidbid))
  return "", {}

### extension, as os.path.splitext ignore leading dots so ".plexignore" file is splitted into ".plexignore" and "" ###
def extension(file):  return file[1:] if file.count('.')==1 and file.startswith('.') else os.path.splitext(file)[1].lstrip('.').lower()

### Make sure the path is unicode, if it is not, decode using OS filesystem's encoding ###
def sanitize_path(p):
  if not isinstance(p, unicode):
    return p.decode(sys.getfilesystemencoding())
  return p

def romanToInt(s):
  roman  = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000,'IV':4,'IX':9,'XL':40,'XC':90,'CD':400,'CM':900}
  i, num = 0, 0
  while i < len(s):
    if i+1<len(s) and s[i:i+2] in roman:  num+=roman[s[i:i+2]];  i +=2
    else:                                 num+=roman[s[i]]    ;  i +=1
  return num

### Look for episodes ###################################################################################
def Scan(path, files, media, dirs, language=None, root=None, **kwargs): #get called for root and each root folder, path relative files are filenames, dirs fullpath
  setup()  # Call setup to get core info. If setup is already done, it just returns and does nothing.
  #if not files:  return  #Residual grouping folder subfolders clear
  
  # Sanitize all path
  msg          = [u"Scan() - dirs: {}, files: {}".format(len(dirs or []), len(files or []))]
  files        = [sanitize_path(p) for p in files] #unicode
  dirs         = [sanitize_path(p) for p in dirs ] #unicode
  root         = sanitize_path(root)
  path         = sanitize_path(path)
  path_split   = path.split(os.sep)
  reverse_path = list(reversed(path.split(os.sep)))
  log_filename = path.split(os.sep)[0] if path else '_root_'
  #VideoFiles.Scan(path, files, media, dirs, root)  # If enabled does not allow zero size files
    
  ### .plexignore file ###
  plexignore_dirs, plexignore_files, msg, source, id = [], [], [], '', ''
  for index, dir in enumerate(path_split):                                                   #enumerate to have index, which goes from 0 to n-1 for n items
    
    # Process Subdirectory pattern from previous folder(s)
    for entry in plexignore_dirs[:] if index>0 else []:                                      #
      plexignore_dirs.remove(entry)                                                          #  
      if entry.startswith(dir+'/'):                                                          #
        pattern = entry.replace(dir+'/', '')                                                 # msg.append("bazinga, pattern.count('/'): '{}', index+1: '{}', len(path_split): '{}', entry: '{}', dir: '{}', pattern: '{}'".format(pattern.count('/'), index+1, len(path_split), entry, dir, pattern))
        if pattern.count('/')>0:        plexignore_dirs.append(pattern)                      # subfolder match so remove subfolder name and carry on
        elif index+1==len(path_split):  plexignore_files.append(fnmatch.translate(pattern));  msg.append("# - pattern: '{}'".format(pattern)) #Only keep pattern for named folder, not subfolders
    
    # Process file patterns
    file = os.path.join(root, os.sep.join(path_split[1:index+1]), '.plexignore')             #
    if os.path.isfile(file):                                                                 #
      msg.append("# " + file)
      msg.append("".ljust(len(file)+ 2, '-'))
      for pattern in filter(None, read_file(file).splitlines()):                             # loop through each line
        pattern = pattern.strip()                                                            # remove useless spaces at both ends
        if pattern == '' or pattern.startswith('#'):  continue                               # skip comment and emopy lines, go to next for iteration
        msg.append("# - " + pattern)
        if '/' not in pattern:  plexignore_files.append(fnmatch.translate(pattern))          # patterns for this folder and subfolders gets converted and added to files.
        elif pattern[0]!='/':   plexignore_dirs.append (pattern)                             # patterns for subfolders added to folders
      msg.append(''.ljust(157, '-'))
        
  ### bluray/DVD folder management ### # source: https://github.com/doublerebel/plex-series-scanner-bdmv/blob/master/Plex%20Series%20Scanner%20(with%20disc%20image%20support).py
  if len(reverse_path) >= 3 and reverse_path[0].lower() == 'stream' and reverse_path[1].lower() == 'bdmv' or "VIDEO_TS.IFO" in str(files).upper():
    for temp in ['stream', 'bdmv', 'video_ts']:
      if reverse_path[0].lower() == temp:  reverse_path.pop(0)
    ep, disc = clean_string(reverse_path[0], True), True
    if len(reverse_path)>1:  reverse_path.pop(0)  #Log.info(u"BluRay/DVD folder detected - using as equivalent to filename ep: '%s', show: '%s'" % (ep, reverse_path[0]))
  else: disc = False
  
  ### Remove season folder to reduce complexity and use folder as serie name ###
  folder_season, season_folder_first = None, False
  for folder in reverse_path[:-1]:                  # remove root folder from test, [:-1] Doesn't thow errors but gives an empty list if items don't exist, might not be what you want in other cases
    for rx in SEASON_RX:                            # in anime, more specials folders than season folders, so doing it first
      folder_clean = clean_string(folder, no_dash=True, no_underscore=True, no_dot=True)
      folder_clean = folder_clean.replace(reverse_path[-1], "") 
      match = rx.search(folder_clean)               #
      if match:                                     # get season number but Skip last entry in seasons (skipped folders)
        if rx!=SEASON_RX[-1]: 
          if rx==SEASON_RX[-2]: folder_season = romanToInt(match.group('season'))
          else:                 folder_season = int( match.group('season')) if match.groupdict().has_key('season') and match.group('season') else 0 #break
          if len(reverse_path)>=2 and folder==reverse_path[-2]:  season_folder_first = True
        #msg.append(u'Removed season folder: "{}", SEASON_RX index: {}, Season: {}'.format(folder_clean, SEASON_RX.index(rx), folder_season))
        reverse_path.remove(folder)                 # Since iterating slice [:] or [:-1] doesn't hinder iteration. All ways to remove: reverse_path.pop(-1), reverse_path.remove(thing|array[0])
        break
  folder_show = filter_chars(reverse_path[0]) if reverse_path else ""
  
  ### Remove un-needed sub-directories (mathing IGNORE_DIRS_RX) ###
  for dir in dirs[:]:
    for rx in IGNORE_DIRS_RX:                                   # loop rx for folders to ignore
      if rx.match(os.path.basename(dir)):                      # if folder match rx
        msg.append(u"Removed subdir: '{}' match '{}' pattern: '{}'".format(dir, 'IGNORE_DIRS_RX', IGNORE_DIRS_RX.index(rx)))
        dirs.remove(dir)
        break
  #msg.append(u'dirs ({}): {}, Files({}): {}'.format( len(dirs), dirs, len(files), files ))
  
  ### Remove files un-needed (ext not in VIDEO_EXTS, mathing IGNORE_FILES_RX or .plexignore pattern) ###
  for file in sorted(files or [], key=natural_sort_key):  #sorted create list copy allowing deleting in place
    ext = file[1:] if file.count('.')==1 and file.startswith('.') else os.path.splitext(file)[1].lstrip('.').lower()  # Otherwise ".plexignore" file is splitted into ".plexignore" and ""
    if ext in VIDEO_EXTS:
      for rx in IGNORE_FILES_RX + [cic(entry) for entry in plexignore_files]:  # Filter trailers and sample files
        if rx.match(os.path.basename(file)):
          msg.append(u"# File: '{}' match '{}' pattern: '{}'".format(os.path.relpath(file, root), 'IGNORE_FILES_RX' if rx in IGNORE_FILES_RX else '.plexignore', rx))
          files.remove(file)
          break
      #msg.append(u'{}'.format(os.path.relpath(file, root)))
    else:
      files.remove(file)
      msg.append(u"File: '{}' not in '{}'".format(os.path.relpath(file, root), 'VIDEO_EXTS'))
  
      ### ZIP ###
      if ext == 'zip':
        Log.info(file)
        zip_archive = zipfile.ZipFile(file)
        for zip_archive_filename in zip_archive.namelist():
          zext = os.path.splitext(zip_archive_filename)[1][1:]  #zname, zext = ...  #zext = zext[1:]
          if zext in VIDEO_EXTS:
            files.append( zip_archive_filename)  #filecontents = zip_archive.read(zip_archive_filename)
            #Log.info(u'{}'.format(zip_archive_filename)) 
      
      ### 7zip ###
      ### RAR ###
      #import rarfile  https://rarfile.readthedocs.io/en/latest/api.html
      #rar_archive = rarfile.RarFile('myarchive.rar')
      #for rar_archive_filename in rar_archive.infolist():
      #  zname, zext = os.path.splitext(rar_archive_filename.filename); zext = zext[1:]
      #  if zext in VIDEO_EXTS:  files.append(rar_archive_filename.filenamee)  #filecontents = rar_archive.read(rar_archive_filename)

  #Plex folder call skip for Grouping folders with 2+ subfolders
  set_logging(root=root, filename=log_filename+'.filelist.log', mode='a' if path else 'w')  #Logging to *.filelist.log
  #Log.info(u'#1# Call: "{}", path: "{}"'.format('Root' if kwargs else 'Plex', path)) 
  for file in files:  Log.info(u'{}'.format(os.path.relpath(file, root)))                                 #Create filelist
  
  ### Logging ###
  if not kwargs:
    set_logging(root=root, filename='_root_.scanner.log',  mode='a')  #Logging to *.scanner.log
    Log.info(u'Call: "Plex", dirs({:>2}), files({:>3}), path: "{}"'.format(len(dirs), len(files), path))
  
  set_logging(root=root, filename=log_filename+'.scanner.log',  mode='a' if path else 'w')  #Logging to *.scanner.log
  Log.info(u"".ljust(157, '='))
  Log.info(u'Call: "{}", path: "{}", folder_show: "{}", dirs ({}), files ({})'.format('Root' if kwargs else 'Plex', path, folder_show, len(dirs), len(files)))
  #Log.info(u"reverse_path: {}, original value: {}, folder_show: {}".format(reverse_path, list(reversed(path.split(os.sep)))))
  #Log.info(u"{} scan start: {}".format("Grouping folder" if kwargs else "Plex", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")))
  if path and not files:  return
  Log.info(u"".ljust(157, '='))
  if msg:
    for entry in msg:  Log.info(entry)
    Log.info(u"".ljust(157, '='))
  
  array, misc_words, misc_count, mappingList  = (), [], {}, {}
  tvdb_mapping, unknown_series_length         = {}, False
  offset_match, offset_season, offset_episode = None, 0, 0
  if path:
    ### Grouping folders skip , unless single series folder ###
    if not kwargs and len(reverse_path)>1 and not season_folder_first:  
      parent_dir    = os.path.join(root, reverse_path[-1])  # folder at root fullpath
      parent_dir_nb = len([file for dir in os.listdir(parent_dir) if os.path.isdir(os.path.join(parent_dir, dir))]) #How many folders in folder at root
      if len(reverse_path)>1 and parent_dir_nb>1 and "Plex Versions" not in parent_dir and "Optimized for " not in parent_dir: 
        Log.info(u'### Grouping folders skipped, will be handled by root level scan ### [return]')
        Log.info(u"".ljust(157, '='))
        Log.info(u'')
        return  #Grouping folders Plex call, but mess after one season folder is ok
      else: Log.info(u"### Grouping folders, not skipped as single series folder ###")
	  
    ### Forced guid modes ###
    match = SOURCE_IDS.search(folder_show) or (SOURCE_IDS.search(folder_show) if len(reverse_path)>1 else False)
    if match:
      if match.group('yt'):  source, id = 'youtube',             match.group('yt')
      else:                  source, id = match.group('source'), match.group('id') 
      Log.info(u'Forced ID (series folder) - source: "{}", id: "{}"'.format(source, id))
    else:
      for file in SOURCE_ID_FILES:
        file_fullpath = os.path.join(root, os.sep.join(list(reversed(reverse_path))), file)
        if os.path.isfile(file_fullpath):
          source, id = file.rstrip('.id'), read_file(file_fullpath).strip()
          Log.info(u'Forced ID (source file) - source: "{}", id: "{}"'.format(source, id))
          folder_show = "%s [%s-%s]" % (clean_string(reverse_path[0]), os.path.splitext(file)[0], id)
          break
      else:
        if FileBot:
          attr, db, sid = None, "", ""
          for file in files:
            attr = filebot.xattr_metadata(file)
            if attr:
              db, sid = filebot.series_id(attr).split('_')  # db = attr_get(attr, 'seriesInfo', 'database')  # id = attr_get(attr, 'seriesInfo', 'id')  #if attr.get('imdbId'):  db, id = 'movie', movie_id(attr)
              if db in FileBot and sid:  # movies: mid = movie_id(attr), imdb_id = attr.get('imdbId'),tmdb_id = attr.get('tmdbId')
                source, id = FileBot[db], sid
                Log.info(u'FileBot Xattr found, source: {}, id: {}, attr: {}'.format(source, id, attr))
                folder_show = id if source=='tvdb' else "%s [%s-%s]" % (clean_string(reverse_path[0]), source, id)  #or source=='tmdb' in movie scanner
                break
          else:
            Log.info(u'No forced id found in series folder name nor id file')
            source, id = "", ""
            folder_show = folder_show.replace(" - ", " ").split(" ", 2)[2] if folder_show.lower().startswith(("saison","season","series","Book","Livre")) and len(folder_show.split(" ", 2))==3 else clean_string(folder_show) # Dragon Ball/Saison 2 - Dragon Ball Z/Saison 8 => folder_show = "Dragon Ball Z"
    #Log.info(u"".ljust(157, '-'))
    
    ### Calculate offset for season or episode (tvdb 2/3/4 mode's offset_episode adjustment is done after tvdb_mapping is populated) ###
    if source.startswith('tvdb') or source.startswith('anidb'):  # 
      offset_match = SOURCE_ID_OFFSET.search(id)
      if offset_match:
        match_season, match_episode = "", ""
        if offset_match.group('season' ):  match_season  = offset_match.group('season' )
        if offset_match.group('episode'):  match_episode = offset_match.group('episode')
        folder_show, id = folder_show.replace("-"+match_season+match_episode+"]", "]"), offset_match.group('id')
    
    if source.startswith('tvdb'):
      #tvdb2, tvdb3 - Absolutely numbered serie displayed with seasons with episodes re-numbered (tvdb2) or staying absolute (tvdb3, for long running shows without proper seasons like dbz, one piece)
      if source in ('tvdb2', 'tvdb3'): 
        Log.info(u"TVDB season mode ({}) enabled".format(source))
        try:
          #Load series episode pages and group them in one dict
          episodes_json, page = [], 1
          while page not in (None, '', 'null'):
            episodes_json_page = json.loads(read_cached_url(TVDB_API2_EPISODES.format(id, page), foldername=os.path.join('TheTVDB','json',id), filename="episodes_page{}_en.json".format(page)))
            episodes_json.extend(episodes_json_page['data'] if 'data' in episodes_json_page else [])  #Log.Info(u'TVDB_API2_EPISODES: {}, links: {}'.format(TVDB_API2_EPISODES.format(id, page), Dict(episodes_json_page, 'links')))
            page = Dict(episodes_json_page, 'links', 'next')
          
          # SORT JSON EPISODES
          sorted_episodes_json = {}
          for episode_json in episodes_json: sorted_episodes_json['s{:02d}e{:03d}'.format(Dict(episode_json, 'airedSeason'), Dict(episode_json, 'airedEpisodeNumber'))] = episode_json
          sorted_episodes_index_list = sorted(sorted_episodes_json, key=natural_sort_key)  #Log.Info(u'len: {}, sorted_episodes_index_list: {}'.format(len(sorted_episodes_index_list), sorted_episodes_index_list))
          
          # Loop through sorted episodes list
          absolute_number, tvdb_mapping = 0, {}
          for index in sorted_episodes_index_list:
            if Dict(sorted_episodes_json[index], 'airedSeason')>0: #continue
              absolute_number = absolute_number + 1
              tvdb_mapping[int(absolute_number)] = (Dict(sorted_episodes_json[index], 'airedSeason'), Dict(sorted_episodes_json[index], 'airedEpisodeNumber') if source =='tvdb2' else int(absolute_number))
        except Exception as e:  Log.error("json loading issue, Exception: %s" % e)

      #tvdb4 - Absolute numbering in any season arrangements aka saga mode
      elif source=='tvdb4' and folder_season==None:  #1-folders nothing to do, 2-local, 3-online
        try:
          file_fullpath = os.path.join(root, path, "tvdb4.mapping")
          if os.path.isfile(file_fullpath):
            tvdb4_mapping_content = read_file(file_fullpath).strip()
            Log.info(u"TVDB season mode (%s) enabled, tvdb4 mapping file: '%s'" % (id, file_fullpath))
          else:
            tvdb4_mapping_content = etree.fromstring(read_cached_url(ASS_MAPPING_URL).strip()).xpath("/tvdb4entries/anime[@tvdbid='%s']" % id)[0].text.strip()
            Log.info(u"TVDB season mode (%s) enabled, tvdb4 mapping url: '%s'" % (id, ASS_MAPPING_URL))
          for line in filter(None, tvdb4_mapping_content.splitlines()):
            season = line.strip().split("|")
            for absolute_episode in range(int(season[1]), int(season[2])+1):  tvdb_mapping[absolute_episode] = (int(season[0]), int(absolute_episode)) 
            if "(unknown length)" in season[3].lower(): unknown_series_length = True
        except Exception as e:
          tvdb_mapping = {}
          if str(e) == "list index out of range":  Log.error("tvdbid: '%s' not found in online season mapping file" % id)
          else:                                    Log.error("Error opening tvdb4 mapping, Exception: '%s'" % e)
        
      #tvdb5 - TheTVDB to absolute index order
      elif source=='tvdb5':
        tvdb_guid_url = TVDB_API1_URL % id
        Log.info(u"TVDB season mode (%s) enabled, tvdb serie rl: '%s'" % (source, tvdb_guid_url))
        try:
          tvdbanime = etree.fromstring(read_cached_url(tvdb_guid_url, foldername=os.path.join('TheTVDB','json',id), filename="series_en.xml"))
          for episode in tvdbanime.xpath('Episode'):
            if episode.xpath('absolute_number')[0].text:
              mappingList['s%se%s'%(episode.xpath('SeasonNumber')[0].text, episode.xpath('EpisodeNumber')[0].text)] = "s1e%s" % episode.xpath('absolute_number')[0].text
          Log.info(u"mappingList: %s" % str(mappingList))
        except Exception as e:  Log.error("xml loading issue, Exception: '%s''" % e)
      
      if tvdb_mapping:  Log.info(u"unknown_series_length: %s, tvdb_mapping: %s (showing changing seasons/episodes only)" % (unknown_series_length, str({x:tvdb_mapping[x] for x in tvdb_mapping if tvdb_mapping[x]!=(1,x)})))  #[for x in tvdb_mapping if tvdb_mapping[x]!=(1,x)]
      Log.info(u"".ljust(157, '-'))
        
    ### Calculate offset for season or episode (must be done after 'tvdb_mapping' is populated) ###
    if offset_match:  # Can't retest as fist go removed the offset entry from 'id' so just reuse earlier matching results
      match_season, match_episode = "", ""
      if offset_match.group('season' ):  match_season,  offset_season  = offset_match.group('season' ), int(offset_match.group('season' )[1:])-1
      if offset_match.group('episode'):  match_episode, offset_episode = offset_match.group('episode'), int(offset_match.group('episode')[1:])-(1 if int(offset_match.group('episode')[1:])>=0 else 0)
      if tvdb_mapping and match_season!='s0': 
        season_ep1      = min([e[1] for e in tvdb_mapping.values() if e[0] == offset_season+1]) if source in ['tvdb3','tvdb4'] else 1
        offset_episode += list(tvdb_mapping.keys())[list(tvdb_mapping.values()).index((offset_season+1,season_ep1))] - 1
      if offset_season!=0 or offset_episode!=0:
        Log.info(u"Manual file offset - (season: '%s', episode: '%s') -> (offset_season: '%s', offset_episode: '%s')" % (match_season, match_episode, offset_season, offset_episode))
        Log.info(u"".ljust(157, '-'))
    
    ### forced guid modes - anidb2/3/4 (requires ScudLee's mapping xml file) ###
    if source in ["anidb2", "anidb3", "anidb4"]:
      a2_tvdbid = ""
      Log.info(u"AniDB mode (%s) enabled, loading mapping xml file (Local->ASS mod->ScudLee master)" % source)
      
      # Local custom mapping file
      dir = os.path.join(root, path)
      while dir:
        scudlee_filename_custom = os.path.join(dir, ANIDB_TVDB_MAPPING_LOC)
        if os.path.exists( scudlee_filename_custom ):
          try:
            Log.info(u"Loading local custom mapping from local: %s" % scudlee_filename_custom)
            a2_tvdbid, mappingList = anidbTvdbMapping(etree.fromstring(read_file(scudlee_filename_custom)), id)
          except:  Log.info(u"Invalid local custom mapping file content")
          else:    break
        dir = os.path.dirname(dir) if len(dir) > len(root) else ''  # Clear variable if we've just finished processing down to (and including) root
      
      # Online mod mapping file = ANIDB_TVDB_MAPPING_MOD (anime-list-corrections.xml)
      if not a2_tvdbid:
        try:                    a2_tvdbid, mappingList = anidbTvdbMapping(etree.fromstring(read_cached_url(ANIDB_TVDB_MAPPING_MOD, foldername='AnimeLists')), id)
        except Exception as e:  Log.error("Error parsing ASS's file mod content, Exception: '%s'" % e)
      
      # Online mapping file = ANIDB_TVDB_MAPPING (anime-list-master.xml)
      if not a2_tvdbid:
        try:                    a2_tvdbid, mappingList = anidbTvdbMapping(etree.fromstring(read_cached_url(ANIDB_TVDB_MAPPING, foldername='AnimeLists')), id)
        except Exception as e:  Log.error("Error parsing ScudLee's file content, Exception: '%s'" % e)
      
      # Set folder_show from successful mapping
      if a2_tvdbid: folder_show = clean_string(folder_show) + " [tvdb-%s]" % a2_tvdbid
      else: folder_show = clean_string(folder_show) + " [anidb-%s]" % (id)
      Log.info(u"".ljust(157, '-'))
    
    if source in ["anidb3", "anidb4"]:
      a3_tvdbid, season_map, relations_map, max_season, new_season, new_episode = "", {}, {}, 0, '', ''
      Log.info(u"AniDB mode (%s) enabled, loading season and relation mapping for all associated tvdbid entries" % source)
      if source=="anidb3" and Dict(mappingList, 'defaulttvdbseason', default='1') != '0':
        Log.info(u"defaulttvdbseason: '%s', is not season 0 so using unmodified mapping" % Dict(mappingList, 'defaulttvdbseason'))
      else:
        try:
          AniDB_TVDB_mapping_tree     = etree.fromstring(read_cached_url(ANIDB_TVDB_MAPPING,     foldername='AnimeLists'))  # Load ScudLee mapping
          AniDB_TVDB_mapping_tree_mod = etree.fromstring(read_cached_url(ANIDB_TVDB_MAPPING_MOD, foldername='AnimeLists'))  # Load ASS mod mapping
          
          # Override/Add ASS mod entries into ScudLee mapping
          mod_anidbids, mod_anidbid_elem = [], []
          for anime in AniDB_TVDB_mapping_tree_mod.iter('anime'):                              # Store the anidbid & element entries
            mod_anidbids.append(anime.get("anidbid")); mod_anidbid_elem.append(anime)
          for anime in AniDB_TVDB_mapping_tree.iter('anime'):                                  # Go over each ScudLee entry to see if it needs to be replaced
            if anime.get("anidbid") in mod_anidbids:
              index = mod_anidbids.index(anime.get("anidbid"))
              AniDB_TVDB_mapping_tree.replace(anime, mod_anidbid_elem[index])                  # Replace the element from ScudLee with ASS
              del mod_anidbid_elem[index]; del mod_anidbids[index]                             # Delete from the list once replaced
          for anidbid_elem in mod_anidbid_elem:  AniDB_TVDB_mapping_tree.append(anidbid_elem)  # Add in the remaining entries in the list as new
          
          # Find each entry that has the same tvdbid listing and store its max season#
          for anime1 in AniDB_TVDB_mapping_tree.iter('anime'):
            if anime1.get("anidbid") == id and anime1.get('tvdbid').isdigit():
              a3_tvdbid = anime1.get('tvdbid')                                                 # Set the tvdbid found from the anidbid
              for anime2 in AniDB_TVDB_mapping_tree.iter('anime'):                             # Load all anidbid's using the same tvdbid with their max tvdb season#
                if anime2.get('tvdbid') == a3_tvdbid:
                  season_map[anime2.get("anidbid")] = {'min': anime2.get('defaulttvdbseason') or '1', 'max': anime2.get('defaulttvdbseason') or '1'}  # Set the min/max season to the 'defaulttvdbseason'
                  if source=="anidb4" and int(anime2.get('episodeoffset') or '0')>0:  season_map[anime2.get("anidbid")] = {'min': '0', 'max': '0'}    # Force series as special if not starting the TVDB season
                  for season in anime2.iter('mapping'):
                    if season_map[anime2.get("anidbid")]['max'].isdigit() and int(season_map[anime2.get("anidbid")]['max']) < int(season.get("tvdbseason")): 
                      season_map[anime2.get("anidbid")]['max'] = season.get("tvdbseason")      # Update the max season to the largest 'tvdbseason' season seen in 'mapping-list'
          
          # Process if entries are found for the anidbid with a valid tvdbid
          if len(season_map) > 0:
            # Get the max season number from TVDB API
            for episode in etree.fromstring(read_cached_url(TVDB_API1_URL % a3_tvdbid, foldername=os.path.join('TheTVDB','json',a3_tvdbid), filename="series_en.xml")).xpath('Episode'):
              if int(episode.xpath('SeasonNumber')[0].text) > max_season:  max_season = int(episode.xpath('SeasonNumber')[0].text)
            # Set the min/max season to ints & update max value to the next min-1 to handle multi tvdb season anidb entries
            map_min_values = [int(season_map[x]['min']) for x in season_map for y in season_map[x] if y=='min']
            for entry in season_map:
              entry_min, entry_max = int(season_map[entry]['min']), int(season_map[entry]['max'])
              while entry_min!=0 and entry_max+1 not in map_min_values and entry_max < max_season:  entry_max += 1
              season_map[entry] = {'min': entry_min, 'max': entry_max}
            # Generate a relations map using all anidbid's using the same tvdbid stored earlier
            for entry in season_map:
              relations_map[entry] = {}
              for anime in etree.fromstring(read_cached_url(ANIDB_HTTP_API_URL+entry, foldername=os.path.join('AniDB','xml'), filename="%s.xml" % entry)).xpath('/anime/relatedanime/anime'):
                if anime.get('type') in relations_map[entry]: relations_map[entry][anime.get('type')].append(anime.get('id'))  # Additional anidbid with an existing relation type
                else:                                         relations_map[entry][anime.get('type')] = [anime.get('id')]      # First anidbid with a new relation type
            #### Note: Below must match hama (variable names are different but logic matches) ####
            def get_prequel_info(prequel_id):
              #Log.info(u"get_prequel_info(prequel_id) = %s" % prequel_id)
              if source=="anidb3":
                if season_map[prequel_id]['min'] == 0 and 'Prequel' in relations_map[prequel_id] and relations_map[prequel_id]['Prequel'][0] in season_map:
                  a, b = get_prequel_info(relations_map[prequel_id]['Prequel'][0])             # Recurively go down the tree following prequels
                  if not str(a).isdigit():  return ('', '')
                  return (a, b+100) if a < max_season else (a+1, 0)  # If the prequel is < max season, add 100 to the episode number offset: Else, add it into the next new season at episode 0
                if season_map[prequel_id]['min'] == 0:            return ('', '')                              # Root prequel is a special so leave mapping alone as special
                elif season_map[prequel_id]['max'] < max_season:  return (season_map[prequel_id]['max'], 100)  # Root prequel season is < max season so add to the end of the Prequel season
                else:                                             return (max_season+1, 0)                     # Root prequel season is >= max season so add to the season after max
              if source=="anidb4":
                if season_map[prequel_id]['min'] != 1 and 'Prequel' in relations_map[prequel_id] and relations_map[prequel_id]['Prequel'][0] in season_map:
                  a, b = get_prequel_info(relations_map[prequel_id]['Prequel'][0])             # Recurively go down the tree following prequels
                  return (a+1+season_map[prequel_id]['max']-season_map[prequel_id]['min'], 0) if str(a).isdigit() else ('', '')  # Add 1 to the season number and start at episode 0
                return (2, 0) if season_map[prequel_id]['min'] == 1 else ('', '')              # Root prequel is season 1 so start counting up. Else was a sequel of specials only so leave mapping alone
            if source=="anidb3":
              if season_map[id]['min'] == 0 and 'Prequel' in relations_map[id] and relations_map[id]['Prequel'][0] in season_map:
                new_season, new_episode = get_prequel_info(relations_map[id]['Prequel'][0])    # Recurively go down the tree following prequels to a TVDB season non-0 AniDB prequel 
            if source=="anidb4":
              if 'Prequel' in relations_map[id] and relations_map[id]['Prequel'][0] in season_map:
                new_season, new_episode = get_prequel_info(relations_map[id]['Prequel'][0])    # Recurively go down the tree following prequels to the TVDB season 1 AniDB prequel 
          
          #Log.info(u"season_map: %s" % str(season_map)) #Log.info(u"relations_map: %s" % str(relations_map))
          if str(new_season).isdigit():  # A new season & eppisode offset has been assigned 
            mappingList['defaulttvdbseason'], mappingList['episodeoffset'] = str(new_season), str(new_episode)
            for key in mappingList.keys():  # Clear out possible mapping list entries for season 1 to leave the default season and episode offset to be applied while keeping season 0 mapping
              if key.startswith("s1"): del mappingList[key]
            Log.info(u"anidbid: '%s', tvdbid: '%s', max_season: '%s', mappingList: %s, season_map: %s" % (id, a3_tvdbid, max_season, str(mappingList), str(season_map)))
          else: Log.info(u"anidbid: '%s', tvdbid: '%s', max_season: '%s', season_map: %s, no override set so using unmodified mapping" % (id, a3_tvdbid, max_season, str(season_map)))
          if a3_tvdbid: folder_show = clean_string(folder_show) + " [tvdb%s-%s]" % ('' if source=="anidb3" else "6", a3_tvdbid)
          else: folder_show = clean_string(folder_show) + " [anidb-%s]" % (id)
        except Exception as e:  Log.error("Error parsing content, Exception: '%s'" % e)
      Log.info(u"".ljust(157, '-'))

    ### Youtube ###
    def getmtime(name):  return os.path.getmtime(os.path.join(root, path, name))
    if source.startswith('youtube') and len(id)>2 and id[0:2] in ('PL', 'UU', 'FL', 'LP', 'RD'):
      try:                    API_KEY = etree.fromstring(read_file(os.path.join(PLEX_ROOT, 'Plug-in Support', 'Preferences', 'com.plexapp.agents.youtube.xml'))).xpath("/PluginPreferences/YouTube-Agent_youtube_api_key")[0].text.strip()
      except Exception as e:  API_KEY='AIzaSyC2q8yjciNdlYRNdvwbb7NEcDxBkv1Cass';  Log.info(u'exception: {}'.format(e))
      
      ### YouTube-dl -J --dump-single-json Playlist file load ###
      json_playlist_file = os.path.join(root, path, 'Playlist.info.json')  #"{}.info.json".format(id))
      if os.path.exists(json_playlist_file):
        Log.info(u'YouTube-dl Playlist file load {}'.format(os.path.relpath(json_playlist_file, root)))
        json_playlist = Dict(json.loads(read_file(json_playlist_file)), 'entries')
        for file in os.listdir(os.path.join(root, path)):
          if extension(file) not in VIDEO_EXTS or os.path.isdir(os.path.join(root, path, file)):  continue  #files only with video extensions
          for rank, video in enumerate(json_playlist or {}, start=1):
            VideoID = Dict(video, 'id')
            if VideoID and VideoID in file:  add_episode_into_plex(media, os.path.join(root, path, file), root, path, folder_show, int(folder_season if folder_season is not None else 1), rank, Dict(video, 'title'), "", rank, 'YouTube', tvdb_mapping, unknown_series_length, offset_season, offset_episode, mappingList);  break
          else:                              Log.info(u'None of video IDs found in filename: {}'.format(file))# entry["_filename"], entry["playlist_index"], entry['upload_date'], 
        return  #"playlist_title" 
      else:
        
        ### YouTube Playlist API call ###
        YOUTUBE_PLAYLIST_ITEMS = 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50&playlistId={}&key='+API_KEY
        iteration, json_full, json_page = 0, {}, {'nextPageToken': None}
        while 'nextPageToken' in json_page and iteration <= 50:
          url=YOUTUBE_PLAYLIST_ITEMS.format(id)+( '&pageToken='+Dict(json_page, 'nextPageToken') if Dict(json_page, 'nextPageToken') else '')
          Log.info(u'[{:>2}] {}'.format(iteration, url))
          try:                                  json_page = json.loads(read_url(url))
          except Exception as e:                json_page = {};  Log.info(u'exception: {}, url: {}'.format(e, url))
          else:
            if json_full:  json_full['items'].extend(json_page['items'])
            else:          json_full = json_page
          iteration +=1
        Log.info(u'---- count: {}'.format(len(json_full['items']) if json_full and 'items' in json_full else 0))
        if json_full:
          for file in os.listdir(os.path.join(root, path)):
            if extension(file) not in VIDEO_EXTS or os.path.isdir(os.path.join(root, path, file)):  continue  #files only with video extensions
            for rank, video in enumerate(Dict(json_full, 'items') or {}, start=1):
              VideoID = video['snippet']['resourceId']['videoId']
              if VideoID and VideoID in file:
                #Log.info(u'[{}] rank: {:>3} in file: "{}"'.format(VideoID, rank, file))
                add_episode_into_plex(media, os.path.join(root, path, file), root, path, folder_show, int(folder_season if folder_season is not None else 1), rank, video['snippet']['title'].encode('utf8'), "", rank, 'YouTube', tvdb_mapping, unknown_series_length, offset_season, offset_episode, mappingList)
                break
            else:  Log.info(u'None of video IDs found in filename: {}'.format(file))
            return
        else:  Log.info(u'json_full is empty')
    
    ### YouTube Channel ###
    if id.startswith('UC') or id.startswith('HC'):  # or not json_playlist and not json_full and source.startswith('youtube') and len(id)>2 and id[0:2] in ('PL', 'UU', 'FL', 'LP', 'RD')
      files_per_date = sorted([os.path.basename(file) for file in files], key=natural_sort_key if SW_YOUTUBE_DATE else getmtime) #to have latest ep first, add: ", reverse=True"
      Log.info(u'files_per_date: {}'.format(files_per_date))
    else:  files_per_date = []
     
    ### Build misc variable to check numbers in titles ###
    misc, length = "|", 0  # put all filenames in folder in a string to count if ep number valid or present in multiple files ###clean_string was true ###
    files.sort(key=natural_sort_key)
    if folder_show:
      array = (folder_show, clean_string(folder_show), clean_string(folder_show, True), clean_string(folder_show, no_dash=True), clean_string(folder_show, True, no_dash=True))
      for file in files:                     # build misc variable, to avoid numbers in titles if present in multiple filenames
        length2=len(os.path.basename(file))  # http://stackoverflow.com/questions/29776299/aligning-japanese-characters-in-python
        if length<length2: length = length2  # max len longest - dirname(file)
        for prefix in array:                 # remove cleansed folder name from cleansed filename and remove potential space
          if clean_string(file, no_whack=True).lower().startswith(prefix.lower()):  misc+= clean_string(os.path.basename(file).lower().replace(prefix.lower(), " ", 1), True)+"|"; break
        else:   misc+= clean_string(os.path.basename(file), True)+"|"
      for separator in [' ', '.', '-', '_']:  misc = misc.replace(separator, '|') 
      misc = "|".join([s for s in misc.split('|') if s])  #Log.info(u"misc: '%s'" % misc)
      for item in misc.split('|'):  misc_count[item] = misc_count[item]+1 if item in misc_count else 1
      for item in misc_count:
        if item and (misc_count[item] >= len(files) and len(files)>=6 or misc_count[item]== max(misc_count.values()) and max(misc_count.values())>3 ):  misc_words.append(item)
        #misc = misc.replace("|%s|" % item, '|')  #Log.info(u"misc_words: '%s', misc_count: '%s'" % (str(misc_words), str(misc_count)))
      misc_words.sort(key=len, reverse=True)  # Sort by string length so largest words are taken out first so smaller words that are in the larger words are not an issue
      #Log.info(u'misc_count: {}'.format(misc_count))
      #Log.info(u'misc_words: {}'.format(misc_words))
      #Log.info(u''.ljust(157, '-'))
  
  ### File main loop ###
  global COUNTER
  COUNTER, movie_list, AniDB_op, standard_holding, unknown_holding, run_count, anidb_xml = 500, {}, {}, [], [], 1, None
  while True:
    for file in files:
      show, season, ep2, title, year = folder_show, folder_season if folder_season is not None else 1, None, "", ""
      ext = file[1:] if file.count('.')==1 and file.startswith('.') else os.path.splitext(file)[1].lstrip('.').lower()  # Otherwise ".plexignore" file is splitted into ".plexignore" and ""
      if ext not in VIDEO_EXTS:  continue
      
      #DVD/BluRay folders
      if ext=="ifo" and not file.upper()=="VIDEO_TS.IFO":  continue
      if disc:  filename = ep
      else:
        filename = os.path.splitext(os.path.basename(file))[0]
        if not path:  root_filename = filename
        filename = sanitize_path(filename)
      
      ### remove cleansed folder name from cleansed filename or keywords otherwise ###
      if path and run_count == 1:
        if clean_string(file, True, no_dash=True)==clean_string(folder_show, True, no_dash=True):  filename, title  = "01", folder_show                  ### If a file name matches the folder name, place as episode 1
        else:
          for prefix in array:
            if clean_string(filename, no_whack=True).lower().startswith(prefix.lower()):  filename = clean_string(re.sub(prefix, " ", filename, 1, re.IGNORECASE), True); break
          else:
            filename = clean_string(filename)
            for item in misc_words:  filename = re.sub(re.escape(item), " ", filename, 1, re.IGNORECASE) ## need to escape names, otherwise words with certain characters (like c++) will make it think its an invalid regex string
      else:  filename = clean_string(filename)
      ep = filename
      if " - Complete Movie" in ep:  ep = "01"  ### Movies ### If using WebAOM (anidb rename)
      elif len(files)==1 and (not re.search(r"\d+(\.\d+)?", clean_string(filename, True)) or "movie" in ep.lower()+folder_show.lower() or "gekijouban" in ep.lower()+folder_show.lower() or "-m" in folder_show.split()):
        ep, title = "01", folder_show  #if  ("movie" in ep.lower()+folder_show.lower() or "gekijouban" in folder_show.lower()) or "-m" in folder_show.split():  ep, title,      = "01", folder_show                  ### Movies ### If only one file in the folder & contains '(movie|gekijouban)' in the file or folder name
      if folder_show and folder_season >= 1:                                                                                                                                         # 
        for prefix in ("s%d" % folder_season, "s%02d" % folder_season):                                                         #"%s %d " % (folder_show, folder_season), 
          if prefix in ep.lower() or prefix in misc_count and misc_count[prefix]>1:  ep = re.sub(prefix, "", ep, 1, re.IGNORECASE).lstrip()   # Series S2  like transformers (bad naming)  # Serie S2  in season folder, Anidb specials regex doesn't like
      if folder_show and ep.lower().startswith("special") or re.search(r"[^a-z]omake[^a-z]", ep.lower()) or "picture drama" in ep.lower():  season, title = 0, ep.title()                        # If specials, season is 0 and if title empty use as title ### 
      
      if not path:
        root_filename = clean_string(root_filename.split(ep)[0] if ep else root_filename)
        show          = root_filename
        
      ### YouTube Channel numbering ###
      if source.startswith('youtube') and id.startswith('UC'):
        filename, folder_season = os.path.basename(file), 0  # sometime youtube-dl gets bad upload date and sets date to NA, mark these as season 0 (specials) so user notices and can fix if wanted
        if SW_YOUTUBE_DATE:
          match = re.match(r"([12]\d{3}[-. ]?(0[1-9]|1[0-2])[-. ]?(0[1-9]|[12]\d|3[01]))",filename)
          if match:  folder_season = int(filename[0:4])  # file starts with "yyyy-mm-dd" "yyyy.mm.dd" "yyyy mm dd" or "yyyymmdd", so take first four digits as the season year
          Log.info(u'Youtube folder season date {}, season: {}, file: {}'.format("regex" if match else "error set season 0", folder_season, filename))
        else:
          folder_season = time.gmtime(os.path.getmtime(os.path.join(root, path, filename)))[0]  # no info from file or flag not set, revert to original way of reading the file date
          Log.info(u'Youtube folder season gmtime,  season: {}, file: {}'.format(folder_season, filename))
        ep = files_per_date.index(filename)+1 if filename in files_per_date else 0
        standard_holding.append([os.path.join(root, path, filename), root, path, folder_show if id in folder_show else folder_show+'['+id+']', int(folder_season if folder_season is not None else 1), ep, filename, folder_season, ep, 'YouTube', tvdb_mapping, unknown_series_length, offset_season, offset_episode, mappingList])
        continue
        
      ### Date Regex ###
      for rx in DATE_RX:
        match = rx.search(ep)
        if match:
          year, month, day = int(match.group('year')), int(match.group('month')), int(match.group('day'))
          Log.info(u'year: {}, mont: {}, day: {}, ep: {}, file: {}'.format(year, month, day, ep, file))
          continue
          # Use the year as the season.
          #tv_show = Media.Episode(show, year, None, None, None)
          #tv_show.released_at = '%d-%02d-%02d' % (year, month, day)
          #tv_show.parts.append(i)
          #mediaList.append(tv_show)
            
      ### Word search for ep number in scrubbed title ###
      words, loop_completed, rx, is_special = list(filter(None, clean_string(ep, False, no_underscore=True).split())), False, "Word Search", False                    #
      for word in words if path else []:                                                                                                                              #
        ep=word.lower().strip('-.')                                                                                                                                   # cannot use words[words.index(word)] otherwise# if word=='': continue filter prevent "" on double spaces
        if WS_VERSION.search(ep):                                                                                  ep=ep[:-2].rstrip('-.')                            #
        if not ep:                                                                                                 continue                                           #
        for prefix in ["ep", "e", "act", "s"]:                                                                                                                        #
          if ep.startswith(prefix) and len(ep)>len(prefix) and WS_DIGIT.search(ep[len(prefix):]):
            #Log.info(u'misc_count[word]: {}, filename.count(word)>=2: {}'.format(misc_count[word] if word in misc_count else 0, filename.count(word)))
            ep, season = ep[len(prefix):], 0 if prefix=="s" and (word not in misc_count or filename.count(word)==1 and misc_count[word]==1 or filename.count(word)>=2 and misc_count[word]==2) else season  # E/EP/act before ep number ex: Trust and Betrayal OVA-act1 # to solve s00e002 "Code Geass Hangyaku no Lelouch S5 Picture Drama 02 'Stage 3.25'.mkv" "'Stage 3 25'"
            break
        else:
          if '-' in ep and len(filter(None, ep.split('-',1)))==2:                                                                                                     # If separator in string
            if WS_MULTI_EP_SIMPLE.search(ep):                                                                      ep, ep2 = ep.split('-'); break
            if WS_MULTI_EP_COMPLEX.search(ep):                                                                     ep="Skip"; break                                   # if multi ep: make it non digit and exit so regex takes care of it
            elif path and ( ( (ep in misc_count and misc_count[ep]==1) and len(files)>=2) or ep not in clean_string(folder_show, True).lower().split() ):
              ep = ep.split('-',1)[0] if ''.join(letter for letter in ep.split('-',1)[0] if letter.isdigit()) else ep.split('-',1)[1]                                 # otherwise all after separator becomes word#words.insert(words.index(word)+1, "-".join(ep.split("-",1)[1:])) #.insert(len(a), x) is equivalent to a.append(x). #???
            else:                                                                                                  continue
          if WS_SPECIALS.search(ep):                                                                               is_special = True; break                           # Specials go to regex # 's' is ignored as dealt with later in prefix processing # '(t|o)' require a number to make sure a word is not accidently matched
          if ''.join(letter for letter in ep if letter.isdigit())=="":                                             continue                                           # Continue if there are no numbers in the string
          if path and ep in misc_count and misc_count[ep]>=2:                                                      continue                                           # Continue if not root folder and string found in in any other filename
          if ep in clean_string(folder_show, True).split() and clean_string(filename, True).split().count(ep)!=2:  continue                                           # Continue if string is in the folder name & string is not in the filename only twice
          #if   ep.isdigit() and len(ep)==4 and (int(ep)< 1900 or folder_season and int(ep[0:2])==folder_season):   season, ep = int(ep[0:2]), ep[2:4]                 # 1206 could be season 12 episode 06  #Get assigned from left ot right
          #elif ep.isdigit() and len(ep)==4:  filename = clean_string( " ".join(words).replace(ep, "(%s)" % ep));   continue                                           # take everything after supposed episode number
          if   ep.isdigit() and len(ep)==4 and int(ep)>= 1930: filename = clean_string( " ".join(words).replace(ep, "(%s)" % ep));   continue                                           # take everything after supposed episode number
        if "." in ep and ep.split(".", 1)[0].isdigit() and ep.split(".")[1].isdigit():                             season, ep, title = 0, ep.split(".", 1)[0], "Special " + ep; break # ep 12.5 = "12" title "Special 12.5"
        title = clean_string( " ".join(words[words.index(word):])[" ".join(words[words.index(word):]).lower().index(ep)+len(ep):] )                                   # take everything after supposed episode number
        break
      else:  loop_completed = True
      
      ### Check for movies at root ###
      if not path:
        if " - Complete Movie" in file:
          ep, title, show, loop_completed = "01", ep.split(" - Complete Movie")[0], ep.split(" - Complete Movie")[0], False    # root folder and movie    
        else:
          match = MOVIE_RX.search(ep)
          if match:  ep, title, year, loop_completed = "01", match.group('show'), match.group('year'), False
       
      if not loop_completed and ep.isdigit():
        standard_holding.append([file, root, path, show, season, int(ep), title, year, int(ep2) if ep2 and ep2.isdigit() else None, rx, tvdb_mapping, unknown_series_length, offset_season, offset_episode, mappingList])
        continue
      
      ### Check for Regex: SERIES_RX + ANIDB_RX ###
      ep = filename
      for rx in ANIDB_RX if is_special else (SERIES_RX + ANIDB_RX):
        match = rx.search(ep)
        if match:
          if match.groupdict().has_key('ep'    ) and match.group('ep'    ):               ep     = match.group('ep')
          elif rx in ANIDB_RX:                                                            ep     = "01"
          else:
            movie_list[season] = movie_list[season]+1 if season in movie_list else 1
            ep     = str(movie_list[season])                              # if no ep in regex and anidb special#add movies using year as season, starting at 1  # Year alone is season Year and ep incremented, good for series, bad for movies but cool for movies in series folder...
            Log.info(u'movie - '+ep)
          if match.groupdict().has_key('ep2'   ) and match.group('ep2'   ):               ep2    =               match.group('ep2'   )                  #
          if match.groupdict().has_key('show'  ) and match.group('show'  ) and not path:  show   = clean_string( match.group('show'  ))                 # Mainly if file at root or _ folder
          if match.groupdict().has_key('season') and match.group('season'):               season =          int( match.group('season'))                 #
          if match.groupdict().has_key('title' ) and match.group('title' ):               title  = clean_string( match.group('title' ))                 #
          elif rx in ANIDB_RX:                                                            title  = ANIDB_TYPE[ANIDB_RX.index(rx)] + ' ' + ep            # Dingmatt fix for opening with just the ep number
          
          if rx in ANIDB_RX[:-1]:                                                                                                                       ### AniDB Specials ################################################################
            season = 0                                                                                                                                  # offset = 100 for OP, 150 for ED, etc... #Log.info(u"ep: '%s', rx: '%s', file: '%s'" % (ep, rx, file))
            # AniDB xml load (ALWAYS GZIPPED)
            if source.startswith('anidb') and id and anidb_xml is None and rx in ANIDB_RX[1:3]:  #2nd and 3rd rx
              anidb_str = read_cached_url(ANIDB_HTTP_API_URL+id, foldername=os.path.join('AniDB','xml'), filename="%s.xml" % id)
              anidb_xml = etree.fromstring( anidb_str )
              
              #Build AniDB_op
              AniDB_op = {}
              for episode in anidb_xml.xpath('/anime/episodes/episode'):
                for epno      in episode.iterchildren('epno' ):  type, epno = epno.get('type'), epno.text
                for title_tag in episode.iterchildren('title'):  title_     = title_tag.text
                if type=='3':
                  index=0
                  if title_.startswith('Opening '):  epno, index = title_.lstrip('Opening '), 1
                  if title_.startswith('Ending ' ):  epno, index = title_.lstrip('Ending  '), 2
                  Log.info(u'type: {}, epno: {}, title: {}, ANIDB_RX.index(rx): {}'.format(type, epno, title_, ANIDB_RX.index(rx)))
                  if epno and not epno.isdigit() and len(epno)>1 and epno[:-1].isdigit():                                                                                    ### OP/ED with letter version Example: op2a
                    epno, offsetno = int(epno[:-1]), ord(epno[-1:])-ord('a')
                    if   not index in AniDB_op:                                          AniDB_op[index]       = {epno: offsetno }
                    elif not epno in AniDB_op[index] or offsetno>AniDB_op[index][epno]:  AniDB_op[index][epno] =        offsetno
              Log.info(u"AniDB URL: '{}', length: {}, AniDB_op: {}".format(ANIDB_HTTP_API_URL+id, len(anidb_str), AniDB_op))
              
            ### OP/ED with letter version Example: op2a
            if not ep.isdigit() and len(ep)>1 and ep[:-1].isdigit():  ep, offset = int(ep[:-1]), ord(ep[-1:])-ord('a')
            else:                                                     offset = 0
            if anidb_xml is None:
              if ANIDB_RX.index(rx) in AniDB_op:  AniDB_op[ANIDB_RX.index(rx)]   [ep] = offset # {101: 0 for op1a / 152: for ed2b} and the distance between a and the version we have hereep, offset                         = str( int( ep[:-1] ) ), offset + sum( AniDB_op.values() )                             # "if xxx isdigit() else 1" implied since OP1a for example... # get the offset (100, 150, 200, 300, 400) + the sum of all the mini offset caused by letter version (1b, 2b, 3c = 4 mini offset)
              else:                               AniDB_op[ANIDB_RX.index(rx)] = {ep:   offset}
            cumulative_offset = sum( [ AniDB_op[ANIDB_RX.index(rx)][x] for x in Dict(AniDB_op, ANIDB_RX.index(rx), default={0:0}) if x<ep and ANIDB_RX.index(rx) in AniDB_op and x in AniDB_op[ANIDB_RX.index(rx)] ] )
            ep = ANIDB_OFFSET[ANIDB_RX.index(rx)] + int(ep) + offset + cumulative_offset    # Sum of all prior offsets
            #Log.info(u'ep type offset: {}, ep: {}, offset: {}, cumulative_offset: {}, final ep number: {}'.format(ANIDB_OFFSET[ANIDB_RX.index(rx)], ep, offset, cumulative_offset, ep))
          standard_holding.append([file, root, path, show, int(season), int(ep), title, year, int(ep2) if ep2 and ep2.isdigit() else int(ep), rx, tvdb_mapping, unknown_series_length, offset_season, offset_episode, mappingList])
          break
      if match: continue  # next file iteration
      
      ### Ep not found, adding as season 0 episode 501+ ###
      if " - " in ep and len(ep.split(" - "))>1:  title = clean_string(" - ".join(ep.split(" - ")[1:])).strip()
      COUNTER = COUNTER+1
      #Log.info(u'COUNTER "{}"'.format(COUNTER))
      if not path and not title:  unknown_holding.append([file, root, path, clean_string(root_filename), 1, 1, title or clean_string(filename, False, no_underscore=True), year, "", ""])
      else:                       unknown_holding.append([file, root, path, show if path else title, 0, COUNTER, title or clean_string(filename, False, no_underscore=True), year, "", ""])
    if run_count == 1 and len(files) > 0 and len(unknown_holding) == len(files):
      Log.info(u"[All files were seen as unknown(5XX). Trying one more time without miscellaneous string filtering.]")
      run_count, standard_holding, unknown_holding, COUNTER = run_count + 1, [], [], COUNTER - len(unknown_holding)
    else:  break  #Break out and don't try a second run as not all files are unknown or there are no files
  for entry in standard_holding + unknown_holding:  add_episode_into_plex(media, *entry)
  if files:  Stack.Scan(path, files, media, dirs)
  
  ### Library root level manual call to Grouping folders ###
  if not path:
    Log.info(u"Library root ([R] Series in Grouping folder Root call (uncached), [_] Normal (cached) Plex call, include grouping folder itself, [S][s] Season folders (uppercase for Root call, lowercase for Plex standard Call)")
    folder_count, subfolders = {}, dirs[:]
    while subfolders:  #Allow to add to the list while looping, any other method failed ([:], enumerate)
      full_path = subfolders.pop(0)
      path      = os.path.relpath(full_path, root)
      
      ### Skip path if matching Ignore dirs ###
      for rx in IGNORE_DIRS_RX:               # loop rx for folders to ignore
        if rx.match(os.path.basename(path)):  # if folder match rx
          Log.info(u'{}[!] {} match IGNORE_DIRS_RX pattern [{}]'.format(''.ljust(path.count(os.sep)*4, ' '), os.path.basename(path), IGNORE_DIRS_RX.index(rx)))
          if full_path in dirs:  dirs.remove(full_path)  # Since iterating slice [:] or [:-1] doesn't hinder iteration. All ways to remove: reverse_path.pop(-1), reverse_path.remove(thing|array[0])
          break
      else:
      
        ### Process subfolders ###
        subdir_dirs, subdir_files, folder_count[path] = [], [], 0
        for file in os.listdir(full_path):
          path_item = os.path.join(full_path, file) 
          if os.path.isdir(path_item):
            subdir_dirs.append(path_item)
            subfolders.insert(0, path_item) #subfolders.append(path_item)
            folder_count[path] +=1
          elif extension(file) in VIDEO_EXTS+['zip']:  subdir_files.append(path_item)
        subfolders   = sorted(subfolders, key=natural_sort_key)
        
        ### Extract season and transparent folder from reverse_path ###
        reverse_path, season_folder_first = list(reversed(path.split(os.sep))), False
        season_folder=[]
        for folder in reverse_path[:-1]:                 # remove root folder from test, [:-1] Doesn't thow errors but gives an empty list if items don't exist, might not be what you want in other cases
          folder_clean = clean_string(folder, no_dash=True, no_underscore=True, no_dot=True).replace(os.path.dirname(path), "") 
          for rx in SEASON_RX:                           # in anime, more specials folders than season folders, so doing it first
            if rx.search(folder_clean):                  # get season number but Skip last entry in seasons (skipped folders)
              season_folder.append(folder)
              reverse_path.remove(folder)                # Since iterating slice [:] or [:-1] doesn't hinder iteration. All ways to remove: reverse_path.pop(-1), reverse_path.remove(thing|array[0])
              if rx!=SEASON_RX[-1] and len(reverse_path)>=2 and folder==reverse_path[-2]:  season_folder_first = True
              break
        
        ### Call Grouping folders series ###
        grouping_dir = full_path.rsplit(os.sep, full_path.count(os.sep)-1-root.count(os.sep))[0]
        root_folder  = os.path.relpath(grouping_dir, root).split(os.sep, 1)[0]
        current_dir  = os.path.basename(full_path)
        indent       = path.count(os.sep)*4
        if root_folder==path:
            set_logging(root=root, filename=path.split(os.sep)[0]+'.scanner.log' , mode='w')  #Empty serie folder log
            set_logging(root=root, filename=path.split(os.sep)[0]+'.filelist.log', mode='w')  #Empty filelist     log
            set_logging(root=root, filename=log_filename         +'.scanner.log' , mode='a')  #Set back 
        if len(reverse_path)>1 and not season_folder_first and folder_count[root_folder]>1:  ### Calling Scan for grouping folders only ###
          Log.info(u'{}[{}] {:<{x}}{}'.format(''.ljust(path.count(os.sep)*4, ' '), 'S' if current_dir in season_folder else 'G', current_dir, '({:>3} files)'.format(len(subdir_files)) if subdir_files else '', x=120-indent))
          if subdir_files:
            Scan(path, sorted(subdir_files), media, sorted(subdir_dirs), language=language, root=root, kwargs_trigger=True)  #relative path for dir or it will show only grouping folder series
            set_logging(root=root, filename=log_filename+'.scanner.log', mode='a')  #due to concurrent calls, wouldn't log propertly without setting it back, just in case
        else:  Log.info(u'{}[{}] {:<{x}}{}'.format(''.ljust(indent, ' '), 's' if current_dir in season_folder else '_', current_dir, '({:>3} files)'.format(len(subdir_files)) if subdir_files else '', x=120-indent))
      
    Log.info(u"".ljust(157, '='))
    Log.info(u"Dirs left for normal Plex calls:")
    for dir in dirs:  Log.info(u"[_] {}".format(os.path.relpath(dir, root)))

  Log.info(u"".ljust(157, '='))
  Log.info(u"")
  
### Command line scanner call ###
if __name__ == '__main__':  #command line
  print("Absolute Series Scanner by ZeroQI")
  path  = sys.argv[1]
  files = [os.path.join(path, file) for file in os.listdir(path)]
  media = []
  Scan(path[1:], files, media, [])
  print("Files detected: ", media)
