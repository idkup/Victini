import requests, json

class ChallongeApi:
    def __init__(self, username: str, key: str):
        self._username = username
        self._key = key
        self._tournamentId = 0
        self._tournamentName = ""
        self._tournamentType = ""
        self._url = ""
        self._checkIn = False
        self._started = False
        self._apiUrl = "https://{}:{}@api.challonge.com/v1/".format(username, key)

    def __str__(self):
        return "u wot"

    def byteToObj(self, bytesData):
        dict_str = bytesData.decode("UTF-8").replace("\'", "\"")
        data = json.loads(dict_str)
        return data

    def setId(self, id: int):
        if id == 0:
            self._tournamentId = id
            return True
        if self._tournamentId != 0:
            return False

        self._tournamentId = id

        res = requests.get(self._apiUrl + "tournaments/{}.json".format(id))

        json = self.byteToObj(res.content)

        self.setName(json["tournament"]["name"])
        self.setUrl(json["tournament"]["url"])
        self.setType(json["tournament"]["tournament_type"])

        self.setCheckIn(False if not json["tournament"]["started_checking_in_at"] else True)

        self.setStart(False if not json["tournament"]["started_at"] else True)

        return True

    def getId(self):
        return self._tournamentId

    def setUrl(self, url: str):
        self._url = url

    def getUrl(self):
        return "https://challonge.com/{}".format(self._url)

    def setName(self, name: str):
        self._tournamentName = name

    def getName(self):
        return self._tournamentName

    def setType(self, type: str):
        self._tournamentType = type

    def getType(self):
        return self._tournamentType

    def getCheckIn(self):
        return self._checkIn

    def setCheckIn(self, bool: bool):
        self._checkIn = bool

    def getStart(self):
        return self._started

    def setStart(self, bool: bool):
        self._started = bool

    def create(self, name, url, type="single elimination"):
        if self._tournamentId != 0:
            return False
        res = requests.post(self._apiUrl + "tournaments.json", {"tournament[name]": name, "tournament[tournament_type]": type, "tournament[url]": url})
        self.setName(name)
        self.setType(type)
        self.setUrl(url)
        self.setId(int(self.byteToObj(res.content)["tournament"]["id"]))
        return True

    def check_id(self):
        if self._tournamentId == 0:
            return False
        return True

    def update_name(self, name):
        if not self.check_id():
            return False
        try:
            requests.put(self._apiUrl + "tournaments/{}.json".format(self.getId()), {"tournament[name]": name})
            self.setName(name)
            return True
        except requests.exceptions.RequestException:
            return False

    def update_url(self, url):
        if not self.check_id():
            return False
        try:
            requests.put(self._apiUrl + "tournaments/{}.json".format(self.getId()), {"tournament[url]": url})
            self.setUrl(url)
            return True
        except requests.exceptions.RequestException:
            return False

    def update_type(self, type):
        if not self.check_id():
            return False
        try:
            requests.put(self._apiUrl + "tournaments/{}.json".format(self.getId()), {"tournament[tournament_type]": type})
            self.setType(type)
            return True
        except requests.exceptions.RequestException:
            return False

    def delete(self):
        if not self.check_id():
            return False
        try:
            requests.delete(self._apiUrl + "tournaments/{}.json".format(self.getId()))
            self.setId(0)
            self.setType("")
            self.setUrl("")
            self.setName("")
            return True
        except requests.exceptions.RequestException:
            return False

    def process_check_in(self):
        if not self.check_id() and self.getCheckIn():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/process_check_ins.json".format(self.getId()))
            self.setCheckIn(True)
            return True
        except requests.exceptions.RequestException:
            return False

    def abort_check_in(self):
        if not self.check_id() and not self.getCheckIn():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/abort_check_in.json".format(self.getId()))
            self.setCheckIn(False)
            return True
        except requests.exceptions.RequestException:
            return False

    def start(self):
        if not self.check_id() and self.getStart():
            return False
        try:
            requests.post(self._apiUrl + "tournaments/{}/start.json".format(self.getId()))
            return True
        except requests.exceptions.RequestException:
            return False

    def finalize(self):
        if not self.check_id() and not self.getStart():
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
            dictName[part["participant"]["name"].lower()] = part["participant"]["id"]

    def add_participant(self, name, challonge_name=""):
        if not self.check_id():
            return False
        try:
            if name.lower() in self.get_participants().keys():
                return False
            requests.post(self._apiUrl + "tournaments/{}/participants.json".format(self.getId()), {"participant[name]": name, "participant[challonge_username]": challonge_name})
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

    def update_participant_name(self, username, newName):
        if not self.check_id():
            return False
        id = self.get_participant_id(username)
        try:
            requests.put(self._apiUrl + "tournaments/{}/participants/{}.json".format(self.getId(), id), {"participant[name]": newName})
            return True
        except requests.exceptions.RequestException:
            return False

    def update_participant_challonge_name(self, username, newName):
        if not self.check_id():
            return False
        id = self.get_participant_id(username)
        try:
            requests.put(self._apiUrl + "tournaments/{}/participants/{}.json".format(self.getId(), id), {"participant[challonge_username]": newName})
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

    def update_match(self, winner, scores):
        if not self.check_id():
            return False
        try:
            res = requests.get(self._apiUrl + "tournaments/{]/matches.json".format(self.getId()))
            json = self.byteToObj(res.content)
            id_winner = self.get_participant_id(winner)
            for match in json:
                if match["player1_id"] == id_winner or match["player2_id"] == id_winner and not match["winner_id"]:
                    requests.put(self._apiUrl + "tournaments/{}/macthes/{}.json".format(self.getId(), match["id"]),
                                 {"match[scores_csv]": scores, "match[winner_id]": id_winner})
                    return True

            return False
        except requests.exceptions.RequestException:
            return False
