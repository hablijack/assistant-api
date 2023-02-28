import logging
import subprocess
import urllib

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import feedparser
from rhasspyhermes.nlu import NluIntent
from rhasspyhermes_app import EndSession, HermesApp

_LOGGER = logging.getLogger("Assistant")

scheduler = BackgroundScheduler()

app = HermesApp(
    "Assistant", 
    host="192.168.178.82", 
    port=1883, 
    username="rhasspy"
)

def execute_timer(identifier, minutes, site_id):
    sentence = 'Deine ' + str(minutes) + ' Minuten Erinnerung ist soeben abgelaufen!'
    app.notify(sentence, site_id)
    scheduler.remove_job(identifier)

@app.on_intent("GetNews")
async def get_news(intent: NluIntent):
    # REMOVE OLD MP3 FILE
    subprocess.call(['rm', '-f', '/tmp/tagesschau.mp3'])
    # GET CURRENT TAGESSCHAU AS MP3
    url = 'https://www.tagesschau.de/export/podcast/hi/tagesschau-in-100-sekunden/'
    feed = feedparser.parse(url)
    # EXTRACT MP3-URL AND GET FILE IN /TMP
    mp3_url = feed['entries'][0]['links'][0]['href']
    urllib.request.urlretrieve(mp3_url, '/tmp/tagesschau.mp3')
    # CONVERT MP3 TO WAV FILE IN /TMP
    subprocess.call([
        'ffmpeg', '-i', '/tmp/tagesschau.mp3', 
        '-ac', '1', '-ar', '24000',
        '/tmp/tagesschau.wav'
    ])
    with open('/tmp/tagesschau.wav', "rb") as wavfile:
        input_wav = wavfile.read()
    # PUBLISH WAV TO MQTT
    topic = 'hermes/audioServer/' + intent.site_id + '/playBytes/' + 'tagesschau'
    app.mqtt_client.publish(topic, input_wav)
    # REMOVE WAV FILE
    subprocess.call(['rm', '-f', '/tmp/tagesschau.wav'])
    return EndSession()

@app.on_intent("GetTime")
async def get_time(intent: NluIntent):
    now = datetime.now()
    sentence = "Es ist jetzt " + str(now.hour) + " Uhr"
    if now.minute > 0:  
        sentence += " und " + str(now.minute) + " Minuten"
    return EndSession(sentence)

@app.on_intent("SetTimer")
async def set_timer(intent: NluIntent):
    minutes = intent.slots[0].value['value']
    identifier = 'timer-' + str(minutes) + '-' + intent.site_id
    scheduler.add_job(
        id=identifier,
        func=execute_timer,
        args=[identifier, minutes, intent.site_id],
        trigger='interval', 
        minutes=minutes)
    sentence = 'Ich werde Dich in: ' + str(minutes) + ' Minuten erinnern.'
    return EndSession(sentence)

if __name__ == "__main__":
    scheduler.start()
    app.run()