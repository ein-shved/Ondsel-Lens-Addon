import requests
import json
import os

import Utils

logger = Utils.getLogger(__name__)


class APIClientException(Exception):
    pass


class APIClientAuthenticationException(APIClientException):
    pass


class APIClientConnectionError(APIClientException):
    pass


OK = requests.codes.ok
CREATED = requests.codes.created
UNAUTHORIZED = requests.codes.unauthorized


class APIClient:
    def __init__(
        self, email, password, api_url, lens_url, access_token=None, user=None
    ):
        self.base_url = api_url
        self.lens_url = lens_url

        if access_token is None:
            self.email = email
            self.password = password
            self.access_token = None
            self.user = None
        else:
            self.email = None
            self.password = None
            self.access_token = access_token
            self.user = user

    def authRequired(func):
        def wrapper(self, *args, **kwargs):
            if not self.access_token:
                self._authenticate()

            result = func(self, *args, **kwargs)

            return result

        return wrapper

    def _authenticate(self):
        endpoint = "authentication"

        payload = {
            "strategy": "local",
            "email": self.email,
            "password": self.password,
        }

        headers = {"Content-Type": "application/json"}
        try:
            data = self._post(endpoint, headers=headers, data=json.dumps(payload))
            self.access_token = data["accessToken"]
            self.user = data["user"]
        except requests.exceptions.RequestException as e:
            raise APIClientException(e)
        # _post also throws an APIClientAuthenticationException or an APIClientException

    def _raiseError(self, response, **kwargs):
        "Raise a generic error based on the status code"
        # dump only when debugging is enabled
        self._dump_response(response, **kwargs)
        raise APIClientException(
            f"API request failed with status code {response.status_code}: "
            + response.json()["message"]
        )

    def _delete(self, endpoint, headers={}, params=None):
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Accept"] = "application/json"

        try:
            response = requests.delete(
                f"{self.base_url}/{endpoint}", params=params, headers=headers
            )
        except requests.exceptions.RequestException as e:
            raise APIClientException(e)

        if response.status_code == OK:
            return response.json()
        else:
            self._raiseError(
                response, endpoint=endpoint, headers=headers, params=params
            )

    def _request(self, endpoint, headers={}, params=None):
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Accept"] = "application/json"
        try:
            response = requests.get(
                f"{self.base_url}/{endpoint}", headers=headers, params=params
            )
        except requests.exceptions.RequestException as e:
            raise APIClientException(e)

        if response.status_code == OK:
            return response.json()
        else:
            self._raiseError(
                response, endpoint=endpoint, headers=headers, params=params
            )

    def _post(self, endpoint, headers={}, params=None, data=None, files=None):
        if endpoint != "authentication":
            headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Accept"] = "application/json"
        try:
            logger.debug(f"Posting {endpoint} {data} {files}")
            response = requests.post(
                f"{self.base_url}/{endpoint}", headers=headers, data=data, files=files
            )
        except requests.exceptions.RequestException as e:
            raise APIClientException(e)

        # only _post makes a distinction between the general error and
        # unauthorized because _authenticate makes use of post and unauthorized
        # should be handled differently for the _authenticate function (for
        # example give the user another try to log in).
        if response.status_code in [CREATED, OK]:
            return response.json()
        elif response.status_code == UNAUTHORIZED:
            raise APIClientAuthenticationException("Not authenticated")
        else:
            self._raiseError(
                response, endpoint=endpoint, headers=headers, data=data, files=files
            )

    def _update(self, endpoint, headers={}, data=None, files=None):
        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["Accept"] = "application/json"

        try:
            response = requests.patch(
                f"{self.base_url}/{endpoint}", headers=headers, data=data, files=files
            )
        except requests.exceptions.RequestException as e:
            raise APIClientException(e)

        if response.status_code in [CREATED, OK]:
            return response.json()
        else:
            self._raiseError(
                response, endpoint=endpoint, headers=headers, data=data, files=files
            )

    def _download(self, url, filename):
        try:
            response = requests.get(url)
        except requests.exceptions.RequestException as e:
            raise APIClientException(e)

        if response.status_code == 200:
            # Save file to workspace directory under the user name not the unique name
            with open(filename, "wb") as f:
                f.write(response.content)
            return True
        else:
            self._raiseError(response, url=url, filename=filename)

    def _dump_response(self, response, **kwargs):
        # # make a dictionary out of the keyword arguments
        # callData = {f"{k}": v for k, v in kwargs.items}
        logger.debug("XXXXXX Call Data XXXXXX")
        for key, value in kwargs.items():
            logger.debug(f"{key} {value}")
        logger.debug("XXXXXXXXXXXXXXXXXXXXXXX")

        logger.debug(response)
        logger.debug(f"Status code: {response.status_code}")

        # Access headers
        logger.debug(f"Content-Type: {response.headers['Content-Type']}")

        # Access response body as text
        logger.debug(f"Response body (text): {response.text}")

        if response.headers["Content-Type"].startswith("application/json"):
            # Access response body as JSON
            logger.debug(f"Response body (JSON): {response.json()}")

    @authRequired
    def get_base_url(self):
        return self.lens_url

    # User/Authentication fuctions

    @authRequired
    def get_user(self):
        return self.user

    @authRequired
    def logout(self):
        endpoint = "authentication"
        result = self._delete(endpoint)
        return result

    # Model Functions

    @authRequired
    def getModels(self, params=None):
        paginationparams = {"$limit": 50, "$skip": 0, "isSharedModel": "false"}

        endpoint = "models"
        if params is None:
            params = paginationparams
        else:
            params = {**params, **paginationparams}

        result = self._request(endpoint, params=params)
        models = result["data"]

        return models

    @authRequired
    def getModel(self, modelId):
        endpoint = f"models/{modelId}"

        result = self._request(endpoint)
        return result

    @authRequired
    def createModel(self, fileId):
        print("Creating the model...")
        endpoint = "models"

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "fileId": fileId,
            "shouldStartObjGeneration": False,
            "createSystemGeneratedShareLink": False,
        }

        result = self._post(endpoint, headers=headers, data=json.dumps(payload))

        return result

    @authRequired
    def regenerateModelObj(self, modelId, fileId):
        print("Regenerating the model OBJ... ")
        endpoint = f"models/{modelId}"

        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            # "shouldCommitNewVersion": True,
            "fileId": fileId,
            "shouldStartObjGeneration": True,
            # "createSystemGeneratedShareLink": False,
        }

        result = self._update(endpoint, headers=headers, data=json.dumps(payload))

        return result

    @authRequired
    def deleteModel(self, _id):
        endpoint = f"/models/{_id}"

        result = self._delete(endpoint)
        return result

    # File Objects functions

    @authRequired
    def getFiles(self, params=None):
        paginationparams = {"$limit": 50, "$skip": 0, "isSystemGenerated": "false"}
        endpoint = "file"
        if params is None:
            params = paginationparams
        else:
            params = {**params, **paginationparams}

        result = self._request(endpoint, params=params)
        files = result["data"]

        return files

    @authRequired
    def createFile(self, fileName, fileUpdatedAt, uniqueName, directory, workspace):
        logger.debug(f"Creating file {fileName} in dir {directory}")
        endpoint = "file"

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "custFileName": fileName,
            "shouldCommitNewVersion": True,
            "version": {
                "uniqueFileName": uniqueName,
                "message": "Initial commit",
                "fileUpdatedAt": fileUpdatedAt,
            },
            "directory": directory,
            "workspace": workspace,
        }

        result = self._post(endpoint, headers=headers, data=json.dumps(payload))

        return result

    @authRequired
    def updateFileObj(
        self, fileId, fileUpdatedAt, uniqueFileName, directory, workspace
    ):
        logger.debug(f"updatingFileObj {fileId} in dir {directory}")
        endpoint = f"file/{fileId}"

        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "shouldCommitNewVersion": True,
            "version": {
                "uniqueFileName": uniqueFileName,
                "fileUpdatedAt": fileUpdatedAt,
                "message": "Update from the Ondsel Lens addon",
            },
            "directory": directory,
            "workspace": workspace,
        }

        result = self._update(endpoint, headers=headers, data=json.dumps(payload))

        return result

    @authRequired
    def setVersionActive(self, fileId, versionId):
        logger.debug("setVersionActive")
        endpoint = f"file/{fileId}"

        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "shouldCheckoutToVersion": True,
            "versionId": versionId,
        }

        result = self._update(endpoint, headers=headers, data=json.dumps(payload))

        return result

    @authRequired
    def deleteFile(self, _id):
        endpoint = f"/file/{_id}"

        result = self._delete(endpoint)
        return result

    #  Upload Functions

    @authRequired
    def uploadFileToServer(self, uniqueName, filename):
        logger.debug(f"upload: {filename}")
        # files to be uploaded need to have a unique name generated with uuid
        # (use str(uuid.uuid4()) ) : test.fcstd ->
        # c4481734-c18f-4b8c-8867-9694ae2a9f5a.fcstd
        # Note that this is not a hash but a random identifier.
        endpoint = "upload"

        if not os.path.isfile(filename):
            raise FileNotFoundError

        with open(filename, "rb") as f:
            fileWithUniqueName = (
                uniqueName,
                f,
                "application/octet-stream",
            )

            files = {"file": fileWithUniqueName}
            result = self._post(endpoint, files=files)
            return result

    @authRequired
    def downloadFileFromServer(self, uniqueName, filename):
        endpoint = f"/upload/{uniqueName}"

        response = self._request(endpoint)
        directory = os.path.dirname(filename)
        os.makedirs(directory, exist_ok=True)

        self._download(response["url"], filename)

    # Shared Model Functions

    @authRequired
    def getSharedModels(self, params=None):
        endpoint = "shared-models"

        headers = {
            "Content-Type": "application/json",
        }

        paginationparams = {"$limit": 50, "$skip": 0}

        if params is None:
            params = paginationparams
        else:
            params = {**params, **paginationparams}

        result = self._request(endpoint, headers, params)
        return result["data"]

    @authRequired
    def createSharedModel(self, params):
        endpoint = "shared-models"

        headers = {
            "Content-Type": "application/json",
        }

        result = self._post(endpoint, headers, data=json.dumps(params))
        return result

    @authRequired
    def getSharedModel(self, shareID):
        endpoint = f"shared-models/{shareID}"

        result = self._request(endpoint)
        return result

    @authRequired
    def updateSharedModel(self, fileData):
        endpoint = f"shared-models/{fileData['_id']}"
        headers = {
            "Content-Type": "application/json",
        }

        result = self._update(endpoint, headers=headers, data=json.dumps(fileData))

        return result

    @authRequired
    def deleteSharedModel(self, ShareModelID):
        endpoint = f"shared-models/{ShareModelID}"

        result = self._delete(endpoint)
        return result

    # Workspace functions.
    @authRequired
    def getWorkspaces(self, params=None):
        paginationparams = {"$limit": 50, "$skip": 0}
        endpoint = "workspaces"
        if params is None:
            params = paginationparams
        else:
            params = {**params, **paginationparams}

        result = self._request(endpoint, params=params)
        workspaces = result["data"]

        return workspaces

    @authRequired
    def getWorkspace(self, workspaceID):
        endpoint = f"workspaces/{workspaceID}"

        result = self._request(endpoint)
        return result

    @authRequired
    def createWorkspace(self, name, description, organizationId):
        print("Creating the workspace...")
        endpoint = "workspaces"

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "name": name,
            "description": description,
            "organizationId": organizationId,
        }

        result = self._post(endpoint, headers=headers, data=json.dumps(payload))

        return result

    @authRequired
    def updateWorkspace(self, workspaceData):
        endpoint = f"workspaces/{workspaceData['_id']}"
        headers = {
            "Content-Type": "application/json",
        }

        result = self._update(endpoint, headers=headers, data=json.dumps(workspaceData))

        return result

    @authRequired
    def deleteWorkspace(self, WorkspaceID):
        endpoint = f"workspaces/{WorkspaceID}"

        result = self._delete(endpoint)
        return result

    # Directory Functions
    @authRequired
    def getDirectories(self, params=None):
        paginationparams = {"$limit": 50, "$skip": 0}
        endpoint = "directories"
        if params is None:
            params = paginationparams
        else:
            params = {**params, **paginationparams}

        result = self._request(endpoint, params=params)
        directories = result["data"]

        return directories

    @authRequired
    def getDirectory(self, directoryID):
        endpoint = f"directories/{directoryID}"

        result = self._request(endpoint)
        return result

    @authRequired
    def createDirectory(self, name, parentDirId, workspace):
        print("Creating the directory...")
        endpoint = "directories"

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "name": name,
            "workspace": workspace,
        }

        result = self._post(endpoint, headers=headers, data=json.dumps(payload))
        dirId = result["_id"]

        payload = {
            "shouldAddDirectoriesToDirectory": True,
            "directoryIds": [dirId],
        }

        result = self._update(
            f"{endpoint}/{parentDirId}", headers=headers, data=json.dumps(payload)
        )

        return dirId

    @authRequired
    def updateDirectory(self, directoryData):
        endpoint = f"directories/{directoryData['_id']}"
        headers = {
            "Content-Type": "application/json",
        }

        result = self._update(endpoint, headers=headers, data=json.dumps(directoryData))

        return result

    @authRequired
    def deleteDirectory(self, directoryID):
        endpoint = f"directories/{directoryID}"

        result = self._delete(endpoint)
        return result


class APIHelper:
    def __init__(self):
        pass

    @staticmethod
    def getFilter(objName):
        if objName == "models":
            return {
                "$limit": None,
                "$skip": None,
                "_id": None,
                "userId": None,
                "custFileName": None,
                "uniqueFileName": None,
                "createdAt": None,
                "updatedAt": None,
                "isSharedModel": None,
                "sharedModelId": None,
                "isSharedModelAnonymousType": None,
            }
        elif objName == "shared-Mode":
            return {
                "$limit": None,
                "$skip": None,
                "_id": None,
                "userId": None,
                "cloneModelId": None,
                "isActive": None,
                "deleted": None,
            }

    @staticmethod
    def filterFilter(data):
        if isinstance(data, dict):
            return {
                key: APIHelper.filterFilter(value)
                for key, value in data.items()
                if value is not None and APIHelper.filterFilter(value)
            }
        elif isinstance(data, list):
            return [
                APIHelper.filterFilter(item)
                for item in data
                if item is not None and APIHelper.filterFilter(item)
            ]
        else:
            return data
