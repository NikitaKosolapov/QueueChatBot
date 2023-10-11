// swift-tools-version: 5.7
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "EMIASQueueBot",
    products: [
        .executable(
        name: "EMIASQueueBot",
        targets: ["EMIASQueueBot"]
    )
    ],
    dependencies: [
        .package(url: "https://github.com/Maxim-Lanskoy/telegram-bot-swift.git", branch: "master"),
    ],
    targets: [
        .executableTarget(
            name: "EMIASQueueBot",
            dependencies: [
                .product(name: "TelegramBotSDK", package: "telegram-bot-swift")
            ])
    ]
)
