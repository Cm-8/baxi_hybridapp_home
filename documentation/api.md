# Baxi HybridApp API
__All the information provided has been gathered through analysis of the source code, traffic from the Baxi HybridApp, and the websites [altuofianco.baxi.it](https://altuofianco.baxi.it/), [hybridweb.baxi.it](https://hybridweb.baxi.it/) and [baxi.servitly.com](https://baxi.servitly.com/), along with extensive online research.__<br>
__Please use this information responsibly.__

## Foreword

_Unlike the MyBaxi app by BAXI (aka BDR Thermea Group), which already has a custom integration available for Home Assistant (see: [remeha_home](https://github.com/msvisser/remeha_home) — known through to [alessandromatera/baxi-node-red](https://github.com/alessandromatera/baxi-node-red)), Baxi's HybridApp relies on the Servitly platform to provide its services._
_For more information about the collaboration between Baxi and Servitly, see: [thanks-to-digitalization-and-servitization-baxi-is-at-the-side-of-its-customers-and-partners](https://www.servitly.com/post/thanks-to-digitalization-and-servitization-baxi-is-at-the-side-of-its-customers-and-partners)_

Servitly offers complete documentation here: https://learn.servitly.com/apidocs/

# The API

## _Location:_
The API used by the Baxi HybridApp app is located at:
```
https://baxi.servitly.com/api/
```
## _Headers:_
All API requests should have the following two headers:
```
Authorization: Bearer <token>
x-semioty-tenant: baxi
```
## _LogIn Endpoint:_
<sup> Ref: https://learn.servitly.com/apidocs/user-login-credentials </sup>
> [!NOTE]
> To obtain the Bearer Token there is an endpoint to which you submit your credentials.

### POST `/identity/users/login?apiKey={{apikey}}`
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
## _LogOut Endpoint:_
<sup> Ref: https://learn.servitly.com/apidocs/user-login-credentials </sup>
> [!NOTE]
> To logout there is an endpoint to which you submit the refreshToken.

### POST `/identity/users/me/logout`
This endpoint is used to logout the user.

_Request Body:_
```json
{"refreshToken":"{{refreshToken}}"}
```
_Response:_
```json
1
```

## _Data Endpoints:_
<sup> Ref: https://learn.servitly.com/apidocs/get-thing-metric-value </sup>
> [!NOTE]
> Each of the following sections gives an example of the output for the different endpoints.


### GET `/data/values?thingId={{thingId}}&pageSize=1&metricName={{metricName}}`
<sup>This endpoint is used to get the system pressure.</sup>

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
