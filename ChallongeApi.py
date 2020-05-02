import requests, json

class api:
    def __init__(self, username: str, key: str):
        self._username = username
        self._key = key
        self._tournamentId = 0
        self._url = ""
        self._apiUrl = "https://{}:{}@api.challonge.com/v1/".format(username, key)

    def __str__(self):
        return "u wot"

    def setId(self, id: int):
        if self._tournamentId != 0:
            return False
        self._tournamentId = id
        return True

    def getId(self):
        return self._tournamentId

    def setUrl(self, url):
        self._url = url

    def getUrl(self):
        return "https://challonge.com/{}".format(self._url)

    def byteToObj(self, bytesData):
        dict_str = bytesData.decode("UTF-8").replace("\'", "\"")
        data = json.loads(dict_str)
        return data

    def create(self, name, url, type="single elimination"):
        if self._tournamentId != 0:
            return False
        res = requests.post(self._apiUrl + "tournaments.json", {"tournament[name]": name, "tournament[tournament_type]": type, "tournament[url]": url})
        print(res.content)
        self.setUrl(url)
        self.setId(int(self.byteToObj(res.content)["tournament"]["id"]))
        return True

    def check_id(self):
        if self._tournamentId == 0:
            return False
        return True

    def update(self):
        if not self.check_id():
            return False
        try:
            requests.put(self._apiUrl + "tournaments/{}.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def delete(self):
        if not self.check_id():
            return False
        try:
            requests.delete(self._apiUrl + "tournaments/{}.json".format(self.getId()))
            self.setId(0)
            return True
        except requests.exceptions.RequestException:
            return False

    def process_check_in(self):
        if not self.check_id():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/process_check_ins.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def abort_check_in(self):
        if not self.check_id():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/abort_check_in.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def start(self):
        if not self.check_id():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/start.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def finalize(self):
        if not self.check_id():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/finalize.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def reset(self):
        if not self.check_id():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/reset.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def get_participants(self):
        if not self.check_id():
            return False
        res = requests.get(self._apiUrl + "tournaments/{}/participants.json".format(self.getId()))
        dictName = {}
        for part in res:
            dictName[part["participant"]["name"]] = part["participant"]["id"]

    def add_participant(self, name, challonge_name=""):
        if not self.check_id():
            return False
        try:
            if name in self.get_participants().keys():
                return False
            requests.post(self._apiUrl + "tournaments/{}/participants.json".format(self.getId()), {"name": name, "challonge_username": challonge_name})
            return True
        except requests.exceptions.RequestException:
            return False

    def get_participant(self, name):
        if not self.check_id():
            return False
        participantsDict = self.get_participants()
        res = requests.get(self._apiUrl + "tournaments/{}/participants/{}.json".format(self.getId(), participantsDict[name]))
        return res

    def get_participant_id(self, name):
        if not self.check_id():
            return False
        participant = self.get_participant(name)
        if not participant:
            return False
        return participant["participant"]["id"]

    def get_participant_name(self, id):
        if not self.check_id():
            return False
        try:
            res = requests.get(self._apiUrl + "tournaments/{}/participants/{}.json".format(self.getId(), id))
            return res["participant"]["name"]
        except requests.exceptions.RequestException:
            return False

    def update_participant_name(self, oldName, newName):
        if not self.check_id():
            return False
        id = self.get_participant_id(oldName)
        try:
            requests.put(self._apiUrl + "tournaments/{}/participants/{}.json".format(self.getId(), id), {"name": newName})
            return True
        except requests.exceptions.RequestException:
            return False

    def update_participant_challonge_name(self, username, newName):
        if not self.check_id():
            return False
        id = self.get_participant_id(username)
        try:
            requests.put(self._apiUrl + "tournaments/{}/participants/{}.json".format(self.getId(), id), {"challonge_username": newName})
            return True
        except requests.exceptions.RequestException:
            return False

    def check_in_participant(self, name):
        if not self.check_id():
            return False
        id = self.get_participant_id(name)
        try:
            requests.post(self._apiUrl + "tournaments/{}/participants/{}/check_in.json".format(self.getId(), id))
            return True
        except requests.exceptions.RequestException:
            return False

    def undo_check_in_participant(self, name):
        if not self.check_id():
            return False
        id = self.get_participant_id(name)
        try:
            requests.post(self._apiUrl + "tournaments/{}/participants/{}/undo_check_in.json".format(self.getId(), id))
            return True
        except requests.exceptions.RequestException:
            return False

    def delete_participant(self, name):
        if not self.check_id():
            return False
        id = self.get_participant_id(name)
        try:
            requests.delete(self._apiUrl + "tournaments/{}/participants/{}.json".format(self.getId(), id))
            return True
        except requests.exceptions.RequestException:
            return False

    def delete_participants(self):
        if not self.check_id():
            return False
        try:
            requests.delete(self._apiUrl + "tournaments/{}/participants/clear.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def randomize_participants(self):
        if not self.check_id():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/participants/randomize.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def list_matches(self):
        if not self.check_id():
            return False
        res = requests.get(self._apiUrl + "tournaments/{}/macthes.json".format(self.getId()))
        return res

    def get_match(self, id):
        if not self.check_id():
            return False
        res = requests.get(self._apiUrl + "tournaments/{}/macthes/{}.json".format(self.getId(), id))
        return res

    def update_match(self, id, scores, winner):
        if not self.check_id():
            return False
        try:
            requests.put(self._apiUrl + "tournaments/{}/macthes/{}.json".format(self.getId(), id), {"scores_csv": scores, "winner_id": self.get_participant_id(winner)})
            return True
        except requests.exceptions.RequestException:
            return False