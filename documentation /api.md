# Baxi HybridApp API
__All of the following information was obtained by sniffing the app traffic.__
__Please use this information responsibly.__

The API used by the Baxi HybridApp app is located at `https://baxi.servitly.com/api/`.

All API requests should have the following two headers:
```
Authorization: Bearer <token>
x-semioty-tenant: baxi
```

***To obtain the Bearer Token there is an endpoint to which you submit your credentials***
## POST `/identity/users/login?apiKey={{apikey}}`
This endpoint is used to get the bearer token.

_Request Body:_
```json
{
  "email": "{{username}}",
  "password": "{{password}}",
  "devices": [
    {
      "deviceId": "{{device_id}}",
      "model": "{{device_model}}",
      "platform": "{{device_platform}}",
      "platformVersion": "{{os_version}}",
      "browser": "{{browser_user_agent}}",
      "notificationDeviceId":"{{notification_device_id}}"
    }
  ]
}
```
_Response:_
```json
{
    "token": "{{token}}",
    "refreshToken": "{{refreshToken}}",
    "userId": "{{userId}}",
    "tenantId": "{{tenantId}}",
    "tokenExpirationTimestamp": 1741236233774
}
```

***To logout there is an endpoint to which you submit the refreshToken***
## POST `/identity/users/me/logout`
This endpoint is used to logout the user.

_Request Body:_
```json
{"refreshToken":"{{refreshToken}}"}
```
_Response:_
```json
1
```

Each of the following sections gives an example of the output for the different endpoints.

## GET `/data/values?thingId={{thingId}}&pageSize=1&metricName={{metricName}}`
This endpoint is used to get the system pressure.

Response:
```json
{
    "data": [
        {
            "timestamp": 1741236233774,
            "values": [
                {
                    "name": "P02A2331",
                    "value": "1.0",
                    "path": "measures",
                    "filled": false
                }
            ]
        }
    ],
    "nextPageToken": null,
    "cacheDisabled": false,
    "aggregation": null
}
```
