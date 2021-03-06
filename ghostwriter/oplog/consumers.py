"""This contains all of the WebSocket consumers used by the Oplog application."""

# Standard Libraries
import json

# Django & Other 3rd Party Libraries
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers import serialize

from .models import OplogEntry


@database_sync_to_async
def getAllLogEntries(oplogId):
    return OplogEntry.objects.filter(oplog_id=oplogId).order_by("start_date")


@database_sync_to_async
def createOplogEntry(oplog_id):
    newEntry = OplogEntry.objects.create(oplog_id_id=oplog_id)
    newEntry.output = ""
    newEntry.save()


@database_sync_to_async
def deleteOplogEntry(oplogEntryId):
    try:
        OplogEntry.objects.get(pk=oplogEntryId).delete()
    except OplogEntry.DoesNotExist:
        pass

@database_sync_to_async
def copyOplogEntry(oplogEntryId):
    entry = OplogEntry.objects.get(pk=oplogEntryId)
    if entry:
        entry.pk = None
        entry.save()


@database_sync_to_async
def editOplogEntry(oplogEntryId, modifiedRow):
    entry = OplogEntry.objects.get(pk=oplogEntryId)

    for key, value in modifiedRow.items():
        setattr(entry, key, value)

    entry.save()


class OplogEntryConsumer(AsyncWebsocketConsumer):
    async def send_oplog_entry(self, event):
        await self.send(text_data=event["text"])

    async def connect(self):
        oplog_id = self.scope["url_route"]["kwargs"]["pk"]
        await self.channel_layer.group_add(str(oplog_id), self.channel_name)
        await self.accept()

        entries = await getAllLogEntries(oplog_id)
        serialized_entries = json.loads(serialize("json", entries))
        message = json.dumps({"action": "sync", "data": serialized_entries})

        await self.channel_layer.group_send(
            str(oplog_id), {"type": "send_oplog_entry", "text": message}
        )

    async def disconnect(self, close_code):
        print(f"[*] Disconnected: {close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        json_data = json.loads(text_data)
        if json_data["action"] == "delete":
            oplog_entry_id = int(json_data["oplogEntryId"])
            await deleteOplogEntry(oplog_entry_id)
        if json_data["action"] == "copy":
            oplog_entry_id = int(json_data["oplogEntryId"])
            await copyOplogEntry(oplog_entry_id)

        if json_data["action"] == "edit":
            oplog_entry_id = int(json_data["oplogEntryId"])
            await editOplogEntry(oplog_entry_id, json_data["modifiedRow"])

        if json_data["action"] == "create":
            await createOplogEntry(json_data["oplog_id"])
