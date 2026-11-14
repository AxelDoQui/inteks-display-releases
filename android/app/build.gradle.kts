plugins {
    id("com.android.application")
}

android {
    namespace = "com.inteks.display"
    compileSdk { version = release(36) { minorApiLevel = 1 } }

    defaultConfig {
        applicationId = "com.inteks.display"
        minSdk = 21
        targetSdk = 28
        versionCode = 1
        versionName = "1.0.84"
    }

    buildTypes {
        release { optimization { enable = false } }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
