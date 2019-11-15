import requests
import git
import os
import time
import shutil
import urllib3
import ast
import json
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEBUG = 5

# syncFrom can be either cvp or git:
#  cvp - configlets are sync'd from cvp to the repo over commiting what's in the repo (CVP is the source of truth)
#  git - configlets are sync'd from git to cvp overwritting what is in CVP (git is the source of truth)
syncFrom = "git"

# Path for git workspace (include trailing /)
gitTempPath = '~/scripts/GitConfiglets/'
gitRepo = 'http://gitlab.tgconrad.com/root/cvp-backups'
gitBranch = 'master'
# Relative path within the repo to the configlet directory, leave blank if they reside in the root
configletPath = ''
ignoreConfiglets = ['.git','.md']
# cvpNodes can be a single item or a list of the cluster
cvpNodes = ['192.168.255.51']
cvpUsername = 'admin'
cvpPassword = 'Arista'

#Requests info for CVP API
connect_timeout = 10
headers = {"Accept": "application/json",
           "Content-Type": "application/json"}
requests.packages.urllib3.disable_warnings()
session = requests.Session()

# CVP API Functions
def login(url_prefix, username, password):
    authdata = {"userId": username, "password": password}
    headers.pop('APP_SESSION_ID', None)
    response = session.post(url_prefix+'/web/login/authenticate.do', data=json.dumps(authdata),
                            headers=headers, timeout=connect_timeout,
                            verify=False)
    cookies = response.cookies
    headers['APP_SESSION_ID'] = response.json()['sessionId']
    if response.json()['sessionId']:
        return response.json()['sessionId']

def logout(url_prefix):
    response = session.post(url_prefix+'/cvpservice/login/logout.do')
    return response.json()

def get_builder(url_prefix,builder_key):
    response = session.get(url_prefix+'/cvpservice/configlet/getConfigletBuilder.do?id='+builder_key)
    return response.json()

def get_configlet_by_name(url_prefix,configlet_name):
    response = session.get(url_prefix+'/cvpservice/configlet/getConfigletByName.do?name='+configlet_name)
    return response.json()

def add_configlet(url_prefix,configlet_name,configlet_body):
    tempData = json.dumps({
          "config": configlet_body,
          "name": configlet_name
    })
    response = session.post(url_prefix+'/cvpservice/configlet/addConfiglet.do', data=tempData)
    return response.json()

def add_configlet_builder(url_prefix,configlet_name,configlet_body):
    tempData = json.dumps({
          "name": configlet_name,
          "data": {
              "main_script": {
                  "data": configlet_body
              }
          }
    })
    response = session.post(url_prefix+'/cvpservice/configlet/addConfigletBuilder.do?isDraft=false', data=tempData)
    return response.json()

def update_configlet(url_prefix,configlet_name,configlet_key,configlet_body):
    tempData = json.dumps({
          "config": configlet_body,
          "key": configlet_key,
          "name": configlet_name
    })
    response = session.post(url_prefix+'/cvpservice/configlet/updateConfiglet.do', data=tempData)
    #return tempData
    return response.json()

def update_configlet_builder(url_prefix,configlet_name,configlet_key,configlet_body):
    tempData = json.dumps({
          "name": configlet_name,
          "data": {
              "main_script": {
                  "data": configlet_body
              }
          },
          "waitForTaskIds": False
    })
    response = session.post(url_prefix+'/cvpservice/configlet/updateConfigletBuilder.do?isDraft=false&id='+configlet_key+'&action=save', data=tempData)
    return response.json()
# End API Calls

# Function to determine if string passed is python or just text
def is_python(code):
   try:
       ast.parse(code)
   except SyntaxError:
       return False
   return True

# Function to sync configlet to CVP
def syncConfiglet(server,configletName,configletConfig):
   try:
      # See if configlet exists
      configlet = get_configlet_by_name(server1,configletName)
      configletKey = configlet['key']
      configletCurrentConfig = configlet['config']
      # For future use to compare date in CVP vs. Git (use this to push to Git)
      configletCurrentDate = configlet['dateTimeInLongFormat']
      # If it does, check to see if the config is in sync, if not update the config with the one in Git
      if configletConfig == configletCurrentConfig:
        if DEBUG > 4:
          print "Configlet", configletName, "exists and is up to date!"
      else:
        update_configlet(server,configletConfig,configletKey,configletName)
        if DEBUG > 4:
          print "Configlet", configletName, "exists and is now up to date"
   except:
      print configletName
      addConfiglet = add_configlet(server,configletName,configletConfig)
      if DEBUG > 4:
        print "Configlet", configletName, "has been added"

##### End of syncConfiglet

def syncConfigletBuilder(server,configletName,configletConfig):
   try:
      # See if configlet exists
      builder = get_configlet_by_name(server,configletName)
      configletKey = builder['key']
      configlet = get_builder(server,configletKey)
      configletCurrentConfig = configlet['data']['main_script']['data']
      # For future use to compare date in CVP vs. Git (use this to push to Git)
      configletCurrentDate = builder['dateTimeInLongFormat']
      # If it does, check to see if the config is in sync, if not update the config with the one in Git
      if configletConfig == configletCurrentConfig:
        if DEBUG > 4:
          print "Configlet", configletName, "exists and is up to date!"
      else:
        update_configlet_builder(server,configletName,configletKey,configletConfig)
        if DEBUG > 4:
          print "Configlet", configletName, "exists and is now up to date"
   except:
      print configletName
      add_configlet_builder(server,configletName,configletConfig)
      if DEBUG > 4:
        print "Configlet", configletName, "has been added"

##### End of syncConfiglet

def cloneRepo():
  # Download/Update the repo
  try:
     if os.path.isdir(gitTempPath):
        shutil.rmtree(gitTempPath)
     repo = git.Repo.clone_from(gitRepo,gitTempPath,branch=gitBranch)
  except:
     print "There was a problem downloading the files from the repo"
#### End of cloneRepo

def syncFromGit(server):
  cloneRepo()

  configlets = os.listdir(gitTempPath + configletPath)
  for configletName in configlets:
     if configletName not in ignoreConfiglets and not configletName.endswith(tuple(ignoreConfiglets)):
        with open(gitTempPath + configletPath + configletName, 'r') as configletData:
           configletConfig=configletData.read()
        if not is_python(configletConfig):
          syncConfiglet(server,configletName,configletConfig)
        else:
          syncConfigletBuilder(server,configletName,configletConfig)

  if os.path.isdir(gitTempPath):
     shutil.rmtree(gitTempPath)
#### End of SyncFromGit
if syncFrom == 'git':
  print "Syncing configlets from git repo to CVP"
  for node in cvpNodes:
      server = 'https://'+node
      login(server,cvpUsername,cvpPassword)
      syncFromGit(server)
      logout(server)
  print "Completed successfully"
else:
  print "Invalid sync option"
