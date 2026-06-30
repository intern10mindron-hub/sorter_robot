// @ts-nocheck
// Qt WebChannel JavaScript API
// This file is part of the Qt WebChannel module.
// Provides JavaScript ↔ Qt/Python communication bridge.

"use strict";

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10,
};

var QWebChannel = function(transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel expects a transport object with a send function and onmessage callback property." +
                      " Given is: transport=" + typeof(transport));
        return;
    }

    var channel = this;
    this.transport = transport;

    this.send = function(data) {
        if (typeof data !== "string") {
            data = JSON.stringify(data);
        }
        channel.transport.send(data);
    };

    this.transport.onmessage = function(message) {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                channel.handleSignal(data);
                break;
            case QWebChannelMessageTypes.response:
                channel.handleResponse(data);
                break;
            case QWebChannelMessageTypes.propertyUpdate:
                channel.handlePropertyUpdate(data);
                break;
            default:
                console.error("invalid message received:", message.data);
                break;
        }
    };

    this.execCallbacks = {};
    this.execId = 0;
    this.exec = function(data, callback) {
        if (!callback) {
            channel.send(data);
            return;
        }
        if (channel.execId === Number.MAX_VALUE) {
            channel.execId = Number.MIN_VALUE;
        }
        if (data.hasOwnProperty("id")) {
            console.error("Cannot exec message with property id: " + JSON.stringify(data));
            return;
        }
        data.id = channel.execId++;
        channel.execCallbacks[data.id] = callback;
        channel.send(data);
    };

    this.objects = {};

    this.handleSignal = function(message) {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("Unhandled signal: " + message.object + "::" + message.signal);
        }
    };

    this.handleResponse = function(message) {
        if (!message.hasOwnProperty("id")) {
            console.error("Invalid response message received: ", JSON.stringify(message));
            return;
        }
        channel.execCallbacks[message.id](message.data);
        delete channel.execCallbacks[message.id];
    };

    this.handlePropertyUpdate = function(message) {
        for (var i = 0; i < message.data.length; ++i) {
            var data = message.data[i];
            var object = channel.objects[data.object];
            if (object) {
                object.propertyUpdate(data.signals, data.properties);
            } else {
                console.warn("Unhandled property update: " + data.object + "::" + data.signal);
            }
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    };

    this.debug = function(message) {
        channel.send({type: QWebChannelMessageTypes.debug, data: message});
    };

    channel.exec({type: QWebChannelMessageTypes.init}, function(data) {
        for (var objectName in data) {
            var objectInfo = data[objectName];
            channel.objects[objectName] = new QObject(objectName, objectInfo, channel);
        }
        for (var name in channel.objects) {
            var object = channel.objects[name];
            object.unwrapProperties();
        }
        if (initCallback) {
            initCallback(channel);
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    });
};

function QObject(name, data, webChannel) {
    this.__id__ = name;
    webChannel.objects[name] = this;

    this.__objectSignals__ = {};
    this.__propertyCache__ = {};

    var object = this;

    this.unwrapProperties = function() {
        for (var propertyIdx in object.__propertyCache__) {
            var property = object.__propertyCache__[propertyIdx];
            if (property instanceof QObject.$Wrapper) {
                object.__propertyCache__[propertyIdx] = webChannel.objects[property.id];
            }
        }
    };

    for (var propertyIdx in data["properties"]) {
        var propertyData = data["properties"][propertyIdx];
        this.addProperty(propertyData[0], propertyData[1], propertyData[2], propertyData[3]);
    }

    for (var methodIdx in data["methods"]) {
        var methodData = data["methods"][methodIdx];
        this.addMethod(methodData[0], methodData[1]);
    }

    for (var signalIdx in data["signals"]) {
        var signalData = data["signals"][signalIdx];
        this.addSignal(signalData[0], signalData[1]);
    }

    for (var name in data["enums"]) {
        this[name] = data["enums"][name];
    }
}

QObject.prototype.addMethod = function(methodName, methodIdx) {
    this[methodName] = function() {
        var args = [];
        var callback;
        for (var i = 0; i < arguments.length; ++i) {
            if (typeof arguments[i] === "function") {
                callback = arguments[i];
            } else {
                args.push(arguments[i]);
            }
        }

        webChannel.exec({
            "type": QWebChannelMessageTypes.invokeMethod,
            "object": object.__id__,
            "method": methodIdx,
            "args": args
        }, function(response) {
            if (response !== undefined) {
                var result = object.unwrapQObject(response);
                if (callback) {
                    (callback)(result);
                }
            } else if (callback) {
                (callback)();
            }
        });
    };

    var object = this;
    var webChannel = this.__webChannel__;
};

QObject.prototype.addSignal = function(signalName, signalIdx) {
    this[signalName] = {
        connect: function(callback) {
            if (typeof callback !== "function") {
                console.error("Bad callback given to connect to signal " + signalName);
                return;
            }
            object.__objectSignals__[signalIdx] = object.__objectSignals__[signalIdx] || [];
            object.__objectSignals__[signalIdx].push(callback);
            if (!signalIdx in object.__propertyCache__) {
                webChannel.exec({
                    type: QWebChannelMessageTypes.connectToSignal,
                    object: object.__id__,
                    signal: signalIdx
                });
            }
        },
        disconnect: function(callback) {
            if (typeof callback !== "function") {
                console.error("Bad callback given to disconnect from signal " + signalName);
                return;
            }
            object.__objectSignals__[signalIdx] = object.__objectSignals__[signalIdx] || [];
            var idx = object.__objectSignals__[signalIdx].indexOf(callback);
            if (idx === -1) {
                console.error("Cannot find connection of signal " + signalName + " to " + callback.name);
                return;
            }
            object.__objectSignals__[signalIdx].splice(idx, 1);
            if (object.__objectSignals__[signalIdx].length === 0) {
                webChannel.exec({
                    type: QWebChannelMessageTypes.disconnectFromSignal,
                    object: object.__id__,
                    signal: signalIdx
                });
            }
        }
    };
    var object = this;
    var webChannel = this.__webChannel__;
};

QObject.prototype.addProperty = function(propertyName, propertyIdx, notifySignalData, propertyValue) {
    this.__propertyCache__[propertyIdx] = propertyValue;

    var object = this;
    var webChannel = this.__webChannel__;

    if (notifySignalData) {
        if (notifySignalData[0] === 1) {
            this.addSignal(notifySignalData[1], notifySignalData[2]);
        } else {
            object[notifySignalData[1]].connect(function() {
                object.__propertyCache__[propertyIdx] = arguments[0];
            });
        }
    }

    Object.defineProperty(this, propertyName, {
        configurable: true,
        get: function() {
            var propertyValue = object.__propertyCache__[propertyIdx];
            if (propertyValue === undefined) {
                console.warn("Undefined value in property cache for property \"" + propertyName + "\" in object " + object.__id__);
            }
            return propertyValue;
        },
        set: function(value) {
            object.__propertyCache__[propertyIdx] = value;
            webChannel.exec({
                type: QWebChannelMessageTypes.setProperty,
                object: object.__id__,
                property: propertyIdx,
                value: value
            });
        }
    });
};

QObject.prototype.signalEmitted = function(signalIdx, signalArgs) {
    var connections = this.__objectSignals__[signalIdx];
    if (connections) {
        for (var i = 0; i < connections.length; ++i) {
            var callback = connections[i];
            callback.apply(callback, signalArgs);
        }
    }
};

QObject.prototype.unwrapQObject = function(response) {
    if (response instanceof Array) {
        var copy = [];
        for (var i = 0; i < response.length; ++i) {
            copy[i] = object.unwrapQObject(response[i]);
        }
        return copy;
    }
    if (!(response instanceof Object)) {
        return response;
    }
    if (!response["__QObject*__"] || !response.id) {
        return response;
    }
    var objectId = response.id;
    if (webChannel.objects[objectId]) {
        return webChannel.objects[objectId];
    }
    var qObject = new QObject(objectId, response.data, webChannel);
    qObject.destroyed.connect(function() {
        if (webChannel.objects[objectId] === qObject) {
            delete webChannel.objects[objectId];
            var destroyedSuffix = " (destroyed)";
            qObject.__id__ += destroyedSuffix;
            for (var name in qObject) {
                var member = qObject[name];
                if (member instanceof Function) {
                    qObject[name] = function() {
                        console.warn("Invoked method of destroyed object " + objectId);
                    };
                }
            }
        }
    });
    return qObject;
};

QObject.$Wrapper = function(id) {
    this.id = id;
};