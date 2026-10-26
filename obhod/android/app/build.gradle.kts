import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Профили регионов общие с Windows-версией: core/regions.json копируется в assets при сборке
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
        minSdk = 29 // hev-socks5-tunnel.aar требует Android 10+
        targetSdk = 35
        versionCode = 5
        versionName = "0.4"
    }

    // Отдельный APK на архитектуру: sing-box весит ~27 МБ на каждую, общий APK вышел бы вдвое больше
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "x86_64")
            isUniversalApk = true
        }
    }

    // Постоянный ключ релизов лежит вне git: <корень репозитория>/keys/keystore.properties.
    // Нет файла (сборка из исходников у другого человека) — подписываем отладочным ключом.
    val releaseProps = rootProject.file("../../keys/keystore.properties")
    signingConfigs {
        if (releaseProps.exists()) {
            val p = Properties().apply { releaseProps.inputStream().use { load(it) } }
            create("release") {
                storeFile = releaseProps.parentFile.resolve(p.getProperty("storeFile"))
                storePassword = p.getProperty("storePassword")
                keyAlias = p.getProperty("keyAlias")
                keyPassword = p.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }

    // sing-box и ByeDPI лежат в jniLibs как lib*.so: только из nativeLibraryDir Android разрешает их запускать
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
    testImplementation("org.json:json:20240303") // в unit-тестах android.jar отдаёт заглушки org.json
}
