plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// ÐŸÑ€Ð¾Ñ„Ð¸Ð»Ð¸ Ñ€ÐµÐ³Ð¸Ð¾Ð½Ð¾Ð² Ð¾Ð±Ñ‰Ð¸Ðµ Ñ Windows-Ð²ÐµÑ€ÑÐ¸ÐµÐ¹: core/regions.json ÐºÐ¾Ð¿Ð¸Ñ€ÑƒÐµÑ‚ÑÑ Ð² assets Ð¿Ñ€Ð¸ ÑÐ±Ð¾Ñ€ÐºÐµ
val sharedAssets = layout.buildDirectory.dir("sharedAssets")
val copyRegions by tasks.registering(Copy::class) {
    from(rootProject.file("../core/regions.json"))
    into(sharedAssets)
}

android {
    namespace = "org.obhod.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "org.obhod.app"
        minSdk = 29 // hev-socks5-tunnel.aar Ñ‚Ñ€ÐµÐ±ÑƒÐµÑ‚ Android 10+
        targetSdk = 35
        versionCode = 4
        versionName = "0.4"
    }

    // ÐžÑ‚Ð´ÐµÐ»ÑŒÐ½Ñ‹Ð¹ APK Ð½Ð° Ð°Ñ€Ñ…Ð¸Ñ‚ÐµÐºÑ‚ÑƒÑ€Ñƒ: sing-box Ð²ÐµÑÐ¸Ñ‚ ~27 ÐœÐ‘ Ð½Ð° ÐºÐ°Ð¶Ð´ÑƒÑŽ, Ð¾Ð±Ñ‰Ð¸Ð¹ APK Ð²Ñ‹ÑˆÐµÐ» Ð±Ñ‹ Ð²Ð´Ð²Ð¾Ðµ Ð±Ð¾Ð»ÑŒÑˆÐµ
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "x86_64")
            isUniversalApk = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("debug") // Ñ‡ÐµÑ€Ð½Ð¾Ð²Ð¸Ðº: Ð¿Ð¾Ð´Ð¿Ð¸ÑÑŒ Ð¾Ñ‚Ð»Ð°Ð´Ð¾Ñ‡Ð½Ñ‹Ð¼ ÐºÐ»ÑŽÑ‡Ð¾Ð¼
        }
    }

    // sing-box Ð¸ ByeDPI Ð»ÐµÐ¶Ð°Ñ‚ Ð² jniLibs ÐºÐ°Ðº lib*.so: Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ð¸Ð· nativeLibraryDir Android Ñ€Ð°Ð·Ñ€ÐµÑˆÐ°ÐµÑ‚ Ð¸Ñ… Ð·Ð°Ð¿ÑƒÑÐºÐ°Ñ‚ÑŒ
    packaging { jniLibs { useLegacyPackaging = true } }

    sourceSets["main"].assets.srcDir(sharedAssets)

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    testOptions { unitTests.isReturnDefaultValues = true }
}

tasks.named("preBuild") { dependsOn(copyRegions) }

dependencies {
    implementation(files("libs/hev-socks5-tunnel.aar"))
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303") // Ð² unit-Ñ‚ÐµÑÑ‚Ð°Ñ… android.jar Ð¾Ñ‚Ð´Ð°Ñ‘Ñ‚ Ð·Ð°Ð³Ð»ÑƒÑˆÐºÐ¸ org.json
}
