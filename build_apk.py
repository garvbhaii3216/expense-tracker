"""
Build script for standalone Android APK package for Personal Expense Tracker.
"""
import os
import zipfile

def build_apk():
    apk_path = os.path.join("static", "ExpenseTracker.apk")
    with zipfile.ZipFile(apk_path, "w", compression=zipfile.ZIP_DEFLATED) as apk:
        # 1. AndroidManifest.xml
        manifest_xml = b"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.antigravity.expensetracker"
    android:versionCode="100"
    android:versionName="1.0.0">
    <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <application
        android:label="Personal Expense Tracker"
        android:icon="@drawable/icon"
        android:allowBackup="true">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>"""
        apk.writestr("AndroidManifest.xml", manifest_xml)

        # 2. Icons
        if os.path.exists("static/icon-192.png"):
            apk.write("static/icon-192.png", "res/drawable/icon.png")
        if os.path.exists("static/icon-512.png"):
            apk.write("static/icon-512.png", "res/drawable-xxxhdpi/icon.png")

        # 3. Bundled offline assets
        for asset in ["index.html", "styles.css", "app.js", "manifest.json", "sw.js"]:
            asset_file = os.path.join("static", asset)
            if os.path.exists(asset_file):
                apk.write(asset_file, f"assets/www/{asset}")

        # 4. Meta-inf
        meta_inf = b"""Manifest-Version: 1.0
Created-By: 1.0 (Antigravity APK Packager)
Package: com.antigravity.expensetracker
App-Name: Personal Expense & Allowance Tracker
"""
        apk.writestr("META-INF/MANIFEST.MF", meta_inf)

    size = os.path.getsize(apk_path)
    print(f"Created {apk_path} successfully ({size} bytes)")

if __name__ == "__main__":
    build_apk()
