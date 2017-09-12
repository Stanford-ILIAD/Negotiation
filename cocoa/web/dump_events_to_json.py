from cocoa.systems.human_system import HumanSystem

__author__ = 'anushabala'
import sqlite3
import json
import math
import os
from cocoa.core.event import Event
from cocoa.core.dataset import Example
from cocoa.core.kb import KB
from argparse import ArgumentParser
from cocoa.core.scenario_db import add_scenario_arguments, ScenarioDB
from cocoa.core.schema import Schema
from cocoa.core.util import read_json, write_json
from datetime import datetime
from collections import defaultdict

date_fmt = '%Y-%m-%d %H-%M-%S'


def convert_events_to_json(chat_id, cursor, scenario_db):
    try:
        cursor.execute('SELECT agent, action, time, data, start_time FROM event WHERE chat_id=? ORDER BY time ASC', (chat_id,))
        logged_events = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute('SELECT agent, action, time, data FROM event WHERE chat_id=? ORDER BY time ASC', (chat_id,))
        logged_events = cursor.fetchall()
        events = []
        for i, (agent, action, time, data) in enumerate(logged_events):
            events.append((agent, action, time, data, time))
        logged_events = events
    cursor.execute('SELECT scenario_id, outcome FROM chat WHERE chat_id=?', (chat_id,))
    result = cursor.fetchone()
    if result is None:
        return None
    (uuid, outcome) = result
    try:
        outcome = json.loads(outcome)
        if 'offer' in outcome:
            if math.isnan(outcome['offer']['price']):
                outcome['offer']['price'] = None
    except ValueError:
        outcome = {'reward': 0}

    try:
        cursor.execute('SELECT agent_types FROM chat WHERE chat_id=?', (chat_id,))
        agent_types = cursor.fetchone()[0]
        agent_types = json.loads(agent_types)
    except sqlite3.OperationalError:
        agent_types = {0: HumanSystem.name(), 1: HumanSystem.name()}

    chat_events = []
    agent_chat = {0: False, 1: False}
    for (agent, action, time, data, start_time) in logged_events:
        if action == 'join' or action == 'leave' or action == 'typing':
            continue
        if action == 'message' and len(data.strip()) == 0:
            continue
        if action == 'select' or action == 'eval':
            data = json.loads(data)
        elif action == 'offer':
            data = json.loads(data)
            if math.isnan(data['price']):
                data['price'] = None
        agent_chat[agent] = True

        time = convert_time_format(time)
        start_time = convert_time_format(start_time)
        event = Event(agent, time, action, data, start_time)
        chat_events.append(event)
    return Example(scenario_db.get(uuid), uuid, chat_events, outcome, chat_id, agent_types)

def single_agent(chat):
    agent_event = {0: 0, 1: 0}
    for event in chat.events:
        agent_event[event.agent] += 1
    return agent_event[0] == 0 or agent_event[1] == 0


def log_transcripts_to_json(scenario_db, db_path, json_path, uids):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # c.execute('''CREATE TABLE event (chat_id text, action text, agent integer, time text, data text)''')
    if uids is None:
        cursor.execute('SELECT DISTINCT chat_id FROM event')
        ids = cursor.fetchall()
    else:
        ids = []
        uids = [(x,) for x in uids]
        for uid in uids:
            cursor.execute('SELECT chat_id FROM mturk_task WHERE name=?', uid)
            ids_ = cursor.fetchall()
            ids.extend(ids_)

    examples = []
    for chat_id in ids:
        # Skip single-agent chat
        ex = convert_events_to_json(chat_id[0], cursor, scenario_db)
        if ex is None:
            continue
        if not single_agent(ex):
            examples.append(ex)

    outfile = open(json_path, 'w')
    json.dump([ex.to_dict() for ex in examples], outfile)
    outfile.close()
    conn.close()


def log_surveys_to_json(db_path, surveys_file):
    import src.config as config

    if config.task == config.MutualFriends:
        questions = ['fluent', 'correct', 'cooperative', 'humanlike', 'comments']
    elif config.task == config.Negotiation:
        questions = ['fluent', 'honest', 'persuasive', 'fair', 'negotiator', 'coherent', 'comments']
    else:
        raise ValueError("Unknown task %s" % config.task)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM survey''')
    logged_surveys = cursor.fetchall()
    survey_data = {}
    agent_types = {}

    for survey in logged_surveys:
        # todo this is pretty lazy - support variable # of questions per task eventually..
        (userid, cid, _, q1, q2, q3, q4, q5, q6, comments) = survey
        responses = dict(zip(questions, [q1, q2, q3, q4, q5, q6, comments]))
        cursor.execute('''SELECT agent_types, agent_ids FROM chat WHERE chat_id=?''', (cid,))
        chat_result = cursor.fetchone()
        agents = json.loads(chat_result[0])
        agent_ids = json.loads(chat_result[1])
        agent_types[cid] = agents
        if cid not in survey_data.keys():
            survey_data[cid] = {0: {}, 1: {}}
        partner_idx = 0 if agent_ids['1'] == userid else 1
        survey_data[cid][partner_idx] = responses

    json.dump([agent_types, survey_data], open(surveys_file, 'w'))


def convert_time_format(time):
    if time is None:
        return time
    try:
        dt = datetime.strptime(time, date_fmt)
        s = str((dt - datetime.fromtimestamp(0)).total_seconds())
        return s
    except (ValueError, TypeError):
        try:
            dt = datetime.fromtimestamp(float(time)) # make sure that time is a UNIX timestamp
            return time
        except (ValueError, TypeError):
            print 'Unrecognized time format: %s' % time

    return None

def read_results_csv(csv_file):
    '''
    Return a dict from mturk_code to worker_id.
    '''
    import csv
    reader = csv.reader(open(csv_file, 'r'))
    header = reader.next()
    worker_idx = header.index('WorkerId')
    code_idx = header.index('Answer.surveycode')
    d = {}
    for row in reader:
        workerid = row[worker_idx]
        code = row[code_idx]
        d[code] = workerid
    return d

def chat_to_worker_id(cursor, code_to_wid):
    '''
    chat_id: {'0': workder_id, '1': worker_id}
    workder_id is None means it's a bot
    '''
    d = {}
    cursor.execute('SELECT chat_id, agent_ids FROM chat')
    for chat_id, agent_uids in cursor.fetchall():
        agent_wid = {}
        agent_uids = eval(agent_uids)
        for agent_id, agent_uid in agent_uids.iteritems():
            if not (isinstance(agent_uid, basestring)): #and agent_uid.startswith('U_')):
                agent_wid[agent_id] = None
            else:
                cursor.execute('''SELECT mturk_code FROM mturk_task WHERE name=?''', (agent_uid,))
                res = cursor.fetchall()
                if len(res) > 0:
                    mturk_code = res[0][0]
                    if mturk_code not in code_to_wid:
                        continue
                    else:
                        agent_wid[agent_id] = code_to_wid[mturk_code]
        d[chat_id] = agent_wid
    return d

def log_worker_id_to_json(db_path, batch_results):
    '''
    {chat_id: {'0': worker_id; '1': worker_id}}
    '''
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    code_to_wid = read_results_csv(batch_results)
    worker_ids = chat_to_worker_id(cursor, code_to_wid)
    output_dir = os.path.dirname(batch_results)
    write_json(worker_ids, output_dir + '/worker_ids.json')


if __name__ == "__main__":
    parser = ArgumentParser()
    add_scenario_arguments(parser)
    parser.add_argument('--db', type=str, required=True, help='Path to database file containing logged events')
    parser.add_argument('--domain', type=str,
                        choices=['MutualFriends', 'Matchmaking'])
    parser.add_argument('--output', type=str, required=True, help='File to write JSON examples to.')
    parser.add_argument('--uid', type=str, nargs='*', help='Only print chats from these uids')
    parser.add_argument('--surveys', type=str, help='If provided, writes a file containing results from user surveys.')
    parser.add_argument('--batch-results', type=str, help='If provided, write a mapping from chat_id to worker_id')
    args = parser.parse_args()
    schema = Schema(args.schema_path, args.domain)
    scenario_db = ScenarioDB.from_dict(schema, read_json(args.scenarios_path))

    log_transcripts_to_json(scenario_db, args.db, args.output, args.uid)
    if args.surveys:
        log_surveys_to_json(args.db, args.surveys)
    if args.batch_results:
        log_worker_id_to_json(args.db, args.batch_results)