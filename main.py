from datetime import datetime,timedelta
from rpc import RPC
from xbmcswift2 import Plugin
from xbmcswift2 import actions
import HTMLParser
import os
import random
import re
import requests
import sqlite3
import time
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import json

from types import *

plugin = Plugin()
big_list_view = False

def log(v):
    xbmc.log(repr(v))


def get_icon_path(icon_name):
    addon_name = xbmcaddon.Addon().getAddonInfo('id')
    if plugin.get_setting('user.icons') == "true":
        user_icon = "special://profile/addon_data/%s/icons/%s.png" % (addon_name,icon_name)
        if xbmcvfs.exists(user_icon):
            return user_icon
    return "special://home/addons/%s/resources/img/%s.png" % (addon_name,icon_name)


def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

@plugin.route('/play/<url>')
def play(url):
    head_tail = url.split('://')
    if len(head_tail) > 1:
        tail = re.sub('//','/',head_tail[1])
        url = "%s://%s" % (head_tail[0],tail)
    xbmc.executebuiltin('PlayMedia("%s")' % url)

@plugin.route('/execute/<url>')
def execute(url):
    xbmc.executebuiltin(url)

@plugin.route('/add_folder')
def add_folder():
    d = xbmcgui.Dialog()
    result = d.input("New Folder")
    if not result:
        return
    folders = plugin.get_storage('folders')
    folders[result] = get_icon_path('folder')
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/remove_folder/<folder>')
def remove_folder(folder):
    folders = plugin.get_storage('folders')
    del folders[folder]
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/change_folder_image/<folder>')
def change_folder_image(folder):
    d = xbmcgui.Dialog()
    result = d.browse(2, 'Choose Image', 'files')
    if not result:
        return
    folders = plugin.get_storage('folders')
    folders[folder] = result
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/add_url/<id>/<label>/<path>/<thumbnail>')
def add_url(id,label,path,thumbnail):
    labels = plugin.get_storage('labels')
    thumbnails = plugin.get_storage('thumbnails')
    urls = plugin.get_storage('urls')
    urls[path] = id
    d = xbmcgui.Dialog()
    result = d.input("Rename Shortcut",label)
    if not result:
        return
    labels[path] = result
    thumbnails[path] = thumbnail
    folders = plugin.get_storage('folders')
    if folders.keys():
        names = ["Top"] + sorted(folders.keys())
        result = d.select("Choose Folder",names)
        if result > 0:
            folder_urls = plugin.get_storage('folder_urls')
            folder_urls[path] = names[result]

@plugin.route('/remove_url/<path>')
def remove_url(path):
    labels = plugin.get_storage('labels')
    thumbnails = plugin.get_storage('thumbnails')
    urls = plugin.get_storage('urls')
    del urls[path]
    del labels[path]
    del thumbnails[path]
    xbmc.executebuiltin('Container.Refresh')


@plugin.route('/change_image/<path>')
def change_image(path):
    d = xbmcgui.Dialog()
    result = d.browse(2, 'Choose Image', 'files')
    if not result:
        return
    thumbnail = result
    thumbnails = plugin.get_storage('thumbnails')
    thumbnails[path] = thumbnail
    xbmc.executebuiltin('Container.Refresh')

@plugin.route('/subscribe_folder/<media>/<id>/<label>/<path>/<thumbnail>')
def subscribe_folder(media,id,label,path,thumbnail):
    folders = plugin.get_storage('folders')
    urls = plugin.get_storage('urls')
    try:
        response = RPC.files.get_directory(media=media, directory=path, properties=["thumbnail"])
    except:
        return
    files = response["files"]
    dirs = dict([[remove_formatting(f["label"]), f["file"]] for f in files if f["filetype"] == "directory"])
    thumbnails = dict([f["file"], f["thumbnail"]] for f in files)
    links = {}
    for f in files:
        if f["filetype"] == "file":
            label = remove_formatting(f["label"])
            file = f["file"]
            while (label in links):
                label = "%s." % label
            links[label] = file

    items = []

    for label in sorted(dirs):
        path = dirs[label]
        file_thumbnail = thumbnails[path]
        if file_thumbnail:
            thumbnail = file_thumbnail
        context_items = []
        if path in folders:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=label.encode("utf8"), path=path, thumbnail=thumbnail))))
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('subscribe_folder',media=media, id=id, label=label.encode("utf8"), path=path, thumbnail=thumbnail),
            'thumbnail': thumbnail,
            'context_menu': context_items,
        })

    for label in sorted(links):
        path = links[label]
        file_thumbnail = thumbnails[path]
        if file_thumbnail:
            thumbnail = file_thumbnail
        context_items = []
        if path in urls:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            path = plugin.url_for('play',url=path)
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=label.encode("utf8"), path=path, thumbnail=thumbnail))))

        items.append(
        {
            'label': label,
            'path': plugin.url_for('play',url=links[label]),
            'thumbnail': thumbnail,
            'context_menu': context_items,
        })

    return items


@plugin.route('/add_addons/<media>')
def add_addons(media):
    folders = plugin.get_storage('folders')
    ids = {}
    for folder in folders:
        id = folders[folder]
        ids[id] = id

    type = "xbmc.addon.%s" % media

    response = RPC.addons.get_addons(type=type,properties=["name", "thumbnail"])
    if "addons" not in response:
        return

    addons = response["addons"]

    items = []

    addons = sorted(addons, key=lambda addon: remove_formatting(addon['name']).lower())
    for addon in addons:
        label = addon['name']
        id = addon['addonid']
        thumbnail = addon['thumbnail']
        path = "plugin://%s" % id
        context_items = []
        if id in ids:
            fancy_label = "[COLOR yellow][B]%s[/B][/COLOR] " % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        else:
            fancy_label = "[B]%s[/B]" % label
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=label.encode("utf8"), path=path, thumbnail=thumbnail))))
        items.append(
        {
            'label': fancy_label,
            'path': plugin.url_for('subscribe_folder',media="files", id=id, label=label, path=path, thumbnail=thumbnail),
            'thumbnail': thumbnail,
            'context_menu': context_items,
        })
    return items

@plugin.route('/favourites')
def favourites():
    urls = plugin.get_storage('urls')

    f = xbmcvfs.File("special://profile/favourites.xml","rb")
    data = f.read()
    favourites = re.findall("<favourite.*?</favourite>",data)
    items = []
    for fav in favourites:
        fav = re.sub('&quot;','',fav)
        url = ''
        thumbnail = ''
        match = re.search('<favourite name="(.*?)" thumb="(.*?)">(.*?)<',fav)
        if match:
            label = match.group(1)
            thumbnail = match.group(2)
            url = match.group(3)
        else:
            match = re.search('<favourite name="(.*?)">(.*?)<',fav)
            if match:
                label = match.group(1)
                thumbnail = ''
                url = match.group(2)
        if url:
            context_items = []
            path = plugin.url_for('execute',url=url)
            if url in urls:
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
            else:
                id = "favourites"
                context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=label.encode("utf8"), path=path, thumbnail=thumbnail))))
            items.append(
            {
                'label': label,
                'path': plugin.url_for('execute',url=url),
                'thumbnail':thumbnail,
                'context_menu': context_items,
            })
    return items

@plugin.route('/add')
def add():
    items = []
    for media in ["video", "music"]:
        label = media
        id = "none"
        path = "library://%s" % media
        thumbnail = get_icon_path(media)
        items.append(
        {
            'label': "[B]%s[/B]" % media.title(),
            'path': plugin.url_for('subscribe_folder',media=media, id=id, label=label, path=path, thumbnail=thumbnail),
            'thumbnail': thumbnail,
        })

    for media in ["video", "audio"]:
        label = media
        thumbnail = get_icon_path(media)
        items.append(
        {
            'label': "[B]%s Addons[/B]" % media.title(),
            'path': plugin.url_for('add_addons',media=media),
            'thumbnail': thumbnail,
        })
    if plugin.get_setting('files.menu') == 'true':
        items.append(
        {
            'label': "[B]%s[/B]" % "Files",
            'path': plugin.url_for('files'),
            'thumbnail':get_icon_path('folder'),
            #'context_menu': context_items,
        })
        items.append(
        {
            'label': "[B]%s[/B]" % "Browse",
            'path': plugin.url_for('browse'),
            'thumbnail':get_icon_path('folder'),
            #'context_menu': context_items,
        })
    items.append(
    {
        'label': "[B]%s[/B]" % "Favourites",
        'path': plugin.url_for('favourites'),
        'thumbnail':get_icon_path('favourites'),
        #'context_menu': context_items,
    })
    items.append(
    {
        'label': "[B]%s[/B]" % "New Folder",
        'path': plugin.url_for('add_folder'),
        'thumbnail':get_icon_path('settings'),
        #'context_menu': context_items,
    })
    if plugin.get_setting('import.export') == 'true':
        items.append(
        {
            'label': "[B]%s[/B]" % "Export",
            'path': plugin.url_for('export_urls'),
            'thumbnail':get_icon_path('settings'),
            #'context_menu': context_items,
        })
        items.append(
        {
            'label': "[B]%s[/B]" % "Import",
            'path': plugin.url_for('import_urls'),
            'thumbnail':get_icon_path('settings'),
            #'context_menu': context_items,
        })
    return items

@plugin.route('/files_folder/<where>')
def files_folder(where):
    urls = plugin.get_storage('urls')
    dirs, files = xbmcvfs.listdir(where)
    items = []
    for d in dirs:
        path = "%s/%s/" % (where,d)
        context_items = []
        if path in urls:
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        else:
            id = "favourites"
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=d, path=path, thumbnail=get_icon_path('folder')))))
        items.append(
        {
            'label': "[B]%s[/B]" % d,
            'path': plugin.url_for('files_folder',where=path),
            'thumbnail':get_icon_path('folder'),
            'context_menu': context_items,
        })
    for f in files:
        path = "%s/%s" % (where,f)
        context_items = []
        if path in urls:
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        else:
            id = "favourites"
            path = plugin.url_for('play',url=path)
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=f, path=path, thumbnail=get_icon_path('file')))))
        items.append(
        {
            'label': f,
            'path': plugin.url_for('play',url=path),
            'thumbnail':get_icon_path('file'),
            'context_menu': context_items,
        })
    return items

@plugin.route('/files')
def files():
    urls = plugin.get_storage('urls')
    d = xbmcgui.Dialog()
    where = d.input('Enter Location (eg c:\ http:// smb:// nfs:// special://)')
    if not where:
        return
    return files_folder(where)

@plugin.route('/browse')
def browse():
    urls = plugin.get_storage('urls')
    d = xbmcgui.Dialog()
    where = d.input('Enter Location (eg c:\ http:// smb:// nfs:// special://)')
    if not where:
        return
    dirs, files = xbmcvfs.listdir(where)
    items = []
    for d in dirs:
        path = "%s%s/" % (where,d)
        context_items = []
        if path in urls:
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        else:
            id = "favourites"
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=d, path=path, thumbnail=get_icon_path('folder')))))
        items.append(
        {
            'label': "[B]%s[/B]" % d,
            'path': path,
            'thumbnail':get_icon_path('folder'),
            'context_menu': context_items,
        })
    for f in files:
        path = "%s/%s" % (where,f)
        context_items = []
        if path in urls:
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        else:
            id = "favourites"
            path = plugin.url_for('play',url=path)
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Add', 'XBMC.RunPlugin(%s)' % (plugin.url_for(add_url, id=id, label=f, path=path, thumbnail=get_icon_path('file')))))
        items.append(
        {
            'label': f,
            'path': plugin.url_for('play',url=path),
            'thumbnail':get_icon_path('file'),
            'context_menu': context_items,
        })
    return items

@plugin.route('/')
def index():
    return folder(None)

@plugin.route('/folder/<folder>')
def folder(folder):
    items = []

    folders = plugin.get_storage('folders')
    folder_urls = plugin.get_storage('folder_urls')
    urls = plugin.get_storage('urls')
    labels = plugin.get_storage('labels')
    thumbnails = plugin.get_storage('thumbnails')

    if not folder:
        for f in sorted(folders):
            thumbnail = folders[f]
            context_items = []
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_folder, folder=f))))
            context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Change Image', 'XBMC.RunPlugin(%s)' % (plugin.url_for(change_folder_image, folder=f))))
            items.append(
            {
                'label': f,
                'path': plugin.url_for('folder', folder=f),
                'thumbnail':thumbnail,
                'context_menu': context_items,
            })
    for url in sorted(urls, key=lambda x: labels[x]):
        if url in folder_urls:
            f = folder_urls[url]
        else:
            f = None
        if f != folder:
            continue
        label = labels[url]
        thumbnail = thumbnails[url]
        path = url
        context_items = []
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Remove', 'XBMC.RunPlugin(%s)' % (plugin.url_for(remove_url, path=path))))
        context_items.append(("[COLOR yellow][B]%s[/B][/COLOR] " % 'Change Image', 'XBMC.RunPlugin(%s)' % (plugin.url_for(change_image, path=path))))
        if path.endswith('/') or path.startswith('plugin://'):
            play_path = path
        else:
            play_path = plugin.url_for('play',url=url)
        items.append(
        {
            'label': label,
            'path': play_path,
            'thumbnail':thumbnail,
            'context_menu': context_items,
        })

    if not folder:
        if plugin.get_setting('kodi.favourites') == 'true':
            f = xbmcvfs.File("special://profile/favourites.xml","rb")
            data = f.read()
            favourites = re.findall("<favourite.*?</favourite>",data)
            for fav in favourites:
                fav = re.sub('&quot;','',fav)
                url = ''
                match = re.search('<favourite name="(.*?)" thumb="(.*?)">(.*?)<',fav)
                if match:
                    label = match.group(1)
                    thumbnail = match.group(2)
                    url = match.group(3)
                else:
                    match = re.search('<favourite name="(.*?)">(.*?)<',fav)
                    if match:
                        label = match.group(1)
                        thumbnail = ''
                        url = match.group(2)
                if url:
                    items.append(
                    {
                        'label': label,
                        'path': plugin.url_for('execute',url=url),
                        'thumbnail':thumbnail,
                    })

    if plugin.get_setting('sort.all') == 'true':
        items = sorted(items, key=lambda item: item['label'])

    items.append(
    {
        'label': "Add",
        'path': plugin.url_for('add'),
        'thumbnail':get_icon_path('settings'),
    })

    view = plugin.get_setting('view.type')
    if view != "default":
        plugin.set_content(view)

    return items

@plugin.route('/import_urls')
def import_urls():
    folders = plugin.get_storage('folders')
    folder_urls = plugin.get_storage('folder_urls')
    urls = plugin.get_storage('urls')
    labels = plugin.get_storage('labels')
    thumbnails = plugin.get_storage('thumbnails')

    if plugin.get_setting('import.clear') == 'true':
        folders.clear()
        folder_urls.clear()
        urls.clear()
        labels.clear()
        thumbnails.clear()

    addon_name = xbmcaddon.Addon().getAddonInfo('id')
    file_name = "special://profile/addon_data/%s/favourites.json" % (addon_name)
    f = xbmcvfs.File(file_name,"rb")

    data = json.loads(f.read())
    log(data)
    for d in data["folders"]:
        folders[d["folder"]] = d["thumbnail"]

    for d in data["favourites"]:
        url = d["url"]
        folder = d["folder"]
        label = d["label"]
        thumbnail = d["thumbnail"]
        id = '' #TODO
        urls[url] = id
        if folder:
            folder_urls[url] = folder
        labels[url] = label
        thumbnails[url] = thumbnail


@plugin.route('/export_urls')
def export_urls():
    folders = plugin.get_storage('folders')
    folder_urls = plugin.get_storage('folder_urls')
    urls = plugin.get_storage('urls')
    labels = plugin.get_storage('labels')
    thumbnails = plugin.get_storage('thumbnails')

    addon_name = xbmcaddon.Addon().getAddonInfo('id')
    file_name = "special://profile/addon_data/%s/favourites.json" % (addon_name)
    f = xbmcvfs.File(file_name,"wb")

    favourite_folders = []
    for folder in folders:
        thumbnail = folders.get(folder,'')
        log((folder,thumbnail))
        favourite_folders.append({"folder":folder,"thumbnail":thumbnail})
    favourites = []
    for url in sorted(urls, key=lambda x: labels[x]):
        folder = folder_urls.get(url,'')
        label = labels[url]
        thumbnail = thumbnails[url]
        log((label,url,folder,thumbnail))
        favourites.append({"label":label,"url":url,"folder":folder,"thumbnail":thumbnail})
    data = {"folders":favourite_folders,"favourites":favourites}
    s = json.dumps(data,indent=2)
    f.write(s)


if __name__ == '__main__':
    plugin.run()
    if big_list_view == True:
        view_mode = int(plugin.get_setting('view_mode'))
        plugin.set_view_mode(view_mode)