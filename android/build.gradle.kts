// AGP 9 trae Kotlin incorporado: NO se aplica org.jetbrains.kotlin.android,
// que fallaria con "Cannot add extension with name 'kotlin'".
plugins {
    id("com.android.application") version "9.2.1" apply false
}
