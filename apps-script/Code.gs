/**
 * Posts new voicemail message ids to the Scribe VM.
 *
 * Script properties:
 *   WEBHOOK_URL     https://<domain>/gmail/notifications
 *   WEBHOOK_SECRET  same value as WEBHOOK_SECRET on the VM
 *
 * Run installTrigger once, then run scribePoll once from the editor to grant consent.
 * The signature is HMAC-SHA256 hex of the raw JSON body, sent as X-Scribe-Signature.
 */
var SCRIBE_QUERY = 'has:attachment (filename:mp3 OR filename:wav OR filename:wave) -label:"scribe/processed" newer_than:2d -in:spam -in:trash';

function scribePoll() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) {
    return;
  }
  try {
    var props = PropertiesService.getScriptProperties();
    var url = props.getProperty('WEBHOOK_URL');
    var secret = props.getProperty('WEBHOOK_SECRET');
    if (!url || !secret) {
      Logger.log('Set WEBHOOK_URL and WEBHOOK_SECRET in Script properties.');
      return;
    }
    var threads = GmailApp.search(SCRIBE_QUERY, 0, 20);
    threads.forEach(function (thread) {
      thread.getMessages().forEach(function (message) {
        postMessage_(url, secret, message.getId());
      });
    });
  } finally {
    lock.releaseLock();
  }
}

function postMessage_(url, secret, messageId) {
  if (!/^[A-Za-z0-9_-]+$/.test(messageId)) {
    Logger.log('skipped a message id with unexpected characters');
    return;
  }
  var body = '{"message_id":"' + messageId + '"}';
  var response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    payload: body,
    headers: {'X-Scribe-Signature': sign_(secret, body)},
    muteHttpExceptions: true,
  });
  var code = response.getResponseCode();
  if (code !== 202) {
    Logger.log('webhook status ' + code + ' message_id=' + messageId);
  }
}

function sign_(secret, body) {
  var bytes = Utilities.computeHmacSha256Signature(body, secret);
  return bytes.map(function (byte) {
    var value = (byte + 256) % 256;
    return ('0' + value.toString(16)).slice(-2);
  }).join('');
}

function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === 'scribePoll') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger('scribePoll').timeBased().everyMinutes(1).create();
}
