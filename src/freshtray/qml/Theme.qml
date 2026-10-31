pragma Singleton
import QtQuick
QtObject {
    property bool dark: false
    property bool compact: false
    readonly property color page: dark ? "#101d2c" : "#f6f8fb"
    readonly property color surface: dark ? "#182a3d" : "#ffffff"
    readonly property color ink: dark ? "#edf4ff" : "#062b54"
    readonly property color muted: dark ? "#a7bad0" : "#657c94"
    readonly property color line: dark ? "#34485f" : "#d6dfe8"
    readonly property color blue: dark ? "#55b4ff" : "#0075dd"
    readonly property color selected: dark ? "#193e60" : "#e8f4ff"
    readonly property color hover: dark ? "#243b52" : "#f0f6fb"
    readonly property color green: dark ? "#189647" : "#008a00"
    readonly property color totalSurface: dark ? "#193b2c" : "#edf7ed"
    readonly property color totalInk: dark ? "#b8e4c4" : "#17682b"
    readonly property color skeleton: dark ? "#2a4057" : "#e5ebf1"
}
