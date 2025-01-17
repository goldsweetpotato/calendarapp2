import streamlit as st
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar
from gcsa.recurrence import Recurrence, DAILY, SU, SA

from beautiful_date import Jan, Apr, Sept
import json
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar
from gcsa.recurrence import Recurrence, DAILY, SU, SA
from google.oauth2 import service_account
from beautiful_date import Jan, Apr, Sept

# gcsa imports
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar
from gcsa.recurrence import Recurrence, DAILY, SU, SA
from google.oauth2 import service_account

# misc imports
from beautiful_date import Jan, Apr, Sept, Oct
import json
import os
from datetime import date, datetime
from beautiful_date import hours

# langchain imports
from langchain_core.runnables.utils import ConfigurableFieldSpec
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents.react.agent import create_react_agent
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool, StructuredTool  # Use the Tool object directly
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.agents import initialize_agent
from langchain.agents import AgentType
from langchain_community.chat_message_histories import (
    StreamlitChatMessageHistory,
)
from langchain_community.callbacks.streamlit import (
    StreamlitCallbackHandler,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
from langchain.callbacks.tracers import ConsoleCallbackHandler
from pydantic import BaseModel, Field


# Deviations from documentation:
# 1- Creating service account and then creating a key for it. (because we the app can't create a server for itself).
# 2- Adding the service account email to your calendar as a user with event edit permissions (from Settings and Sharing) (because we the app can't create a server for itself).
# 3- Using service_account.Credentials.from_service_account_info to get the credenntials instead of credentials_path (for security reasons).
# 4- Putting the JSON in StreamLit secrets and using json.loads rather than uploading the file to github (for security reasons).


# Get the credintials from Secrets.
credentials = service_account.Credentials.from_service_account_info(
        json.loads(st.secrets["FengJson"]),
        scopes=["https://www.googleapis.com/auth/calendar"]
    )

# Create the GoogleCalendar.
calendar = GoogleCalendar(credentials=credentials)

### Event listing tool

# Parameters needed to look for an event
class GetEventargs(BaseModel):
    from_datetime: datetime = Field(description="beginning of date range to retrieve events")
    to_datetime: datetime = Field(description="end of date range to retrieve events")

# Define the tool 
def get_events(from_datetime, to_datetime):
    events = calendar.get_events(calendar_id="mflin@bu.edu", time_min=from_datetime, time_max=to_datetime)
    # print(list(events), from_datetime, to_datetime)
    return list(events)

# Create a Tool object 
list_event_tool = StructuredTool(
    name="GetEvents",
    func=get_events,
    args_schema=GetEventargs,
    description="Useful for getting the list of events from the user's calendar."
)

#------------

#-------
### Event adding tool

# Parameters needed to look for an event
class AddEventargs(BaseModel):
    start_date_time: datetime = Field(description="start date and time of event")
    length_hours: int = Field(description="length of event")
    event_name: str = Field(description="name of the event")


# Define the tool 
def add_event(start_date_time, length_hours, event_name):
    start = start_date_time
    end = start + length_hours * hours
    event = Event(event_name,
                  start=start,
                  end=end)
    return calendar.add_event(event, calendar_id="mflin@bu.edu")

# Create a Tool object 
add_event_tool = StructuredTool(
    name="AddEvent",
    func=add_event,
    args_schema=AddEventargs,
    description="Useful for adding an event with a start date, event name, and length in hours the list of events. Calls get_events to make sure if the new event has been deleted."
)

#------------

##Update this list with the new tools
tools = [list_event_tool, add_event_tool]

#-----------


# Create the LLM
llm = ChatOpenAI(api_key=st.secrets["MyOpenAIkey"], temperature=0.1)

# Messages used by the chatbot
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful Google Calendar assistant"),
        ("human", "{input}"),
        # Placeholders fill up a **list** of messages
        ("placeholder", "{agent_scratchpad}"),
    ]
)


# Creating the agent that will integrate the provided calendar tool with the LLM.
agent = create_tool_calling_agent(llm, tools, prompt)
agent = AgentExecutor(
    agent=agent, 
    tools=tools,
    # verbose=True,
)

#--------------------


# Storing message history
msgs = StreamlitChatMessageHistory(key="special_app_key")

# Load the first AI message
if len(msgs.messages) == 0:
    msgs.add_ai_message("How may I assist you today?")

# Add the rest of the conversation
for msg in msgs.messages:
        if (msg.type in ["ai", "human"]):
                st.chat_message(msg.type).write(msg.content)

# When the user enters a new prompt
if entered_prompt := st.chat_input("What does my day look like?"):
    # Add human message
    st.chat_message("human").write(entered_prompt)
    msgs.add_user_message(entered_prompt)

    # get a response from the agent
    st_callback = StreamlitCallbackHandler(st.container())
    response = agent.invoke({"input": msgs}, {"callbacks": [st_callback, ConsoleCallbackHandler()]})

    # Add AI response.
    response = response["output"]
    st.chat_message("ai").write(response)
    msgs.add_ai_message(response)
