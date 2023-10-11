import Foundation
import TelegramBotSDK

let token = readToken(from: "EMIAS_QUEUE_BOT_TOKEN")
let bot = TelegramBot(token: token)
let router = Router(bot: bot)

struct Queue {
    var queue: [User] = []
    var order = 1
    let topic: Int
}

var iosQueue = Queue(topic: 4122)
var androidQueue = Queue(topic: 4121)

let errorText = "Необходимо выполнить команду в iOS или Android топике"

// Обработчик команды /add
router["add"] = { context in
    guard let user = context.update.message?.from else { return true }
    
    guard !iosQueue.queue.contains(user) && !androidQueue.queue.contains(user) else {
        reply(with: context, text: "Вы уже в очереди")
        return false
    }
    
    var responseText: String = ""
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        iosQueue.queue.append(user)
        responseText += getDeveloperList(with: iosQueue.queue)
    case androidQueue.topic:
        androidQueue.queue.append(user)
        responseText += getDeveloperList(with: androidQueue.queue)
    default:
        reply(with: context, text: errorText)
        return true
    }
    
    reply(with: context, text: responseText)
    
    return true
}

// Обработчик команды /list
router["list"] = { context in
    var responseText: String
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        responseText = iosQueue.queue.isEmpty ? "Очередь пуста" : "В очереди:\n"
        responseText += getDeveloperList(with: iosQueue.queue)
    case androidQueue.topic:
        responseText = androidQueue.queue.isEmpty ? "Очередь пуста" : "В очереди:\n"
        responseText += getDeveloperList(with: androidQueue.queue)
    default:
        reply(with: context, text: errorText)
        return true
    }
    
    reply(with: context, text: responseText)
    return true
}

// Обработчик команды /remove
router["remove"] = { context in
    guard let user = context.update.message?.from else { return true }
    
    guard iosQueue.queue.contains(user) || androidQueue.queue.contains(user) else {
        reply(with: context, text: "Вы не в очереди")
        return false
    }
    
    var responseText: String = ""
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        let indexToRemove = iosQueue.queue.firstIndex(of: user) ?? 0
        iosQueue.queue.remove(at: indexToRemove)
        responseText = iosQueue.queue.isEmpty ? "Очередь пуста" : "В очереди:\n"
        responseText += getDeveloperList(with: iosQueue.queue)
    case androidQueue.topic:
        let indexToRemove = androidQueue.queue.firstIndex(of: user) ?? 0
        androidQueue.queue.remove(at: indexToRemove)
        responseText = androidQueue.queue.isEmpty ? "Очередь пуста" : "В очереди:\n"
        responseText += getDeveloperList(with: androidQueue.queue)
    default:
        reply(with: context, text: errorText)
        return true
    }
    
    reply(with: context, text: responseText)
    
    return true
}

router["clear"] = { context in
    guard let admins = bot.getChatAdministratorsSync(chatId: .chat(context.chatId ?? 0)),
          let id = context.message?.from?.id,
          admins.map({ $0.user.id }).contains(id) else {
        reply(with: context, text: "Очищать очередь может только админ")
        return true
    }
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        iosQueue.queue = []
    case androidQueue.topic:
        androidQueue.queue = []
    default:
        reply(with: context, text: errorText)
        return true
    }
    
    reply(with: context, text: "Очередь очищена")
    
    return true
}

func reply(with context: Context, text: String) {
    context.respondAsync(text, disableNotification: true, replyToMessageId: context.update.message?.messageId, replyMarkup: .forceReply(.init(forceReply: true)))
}

func getDeveloperList(with queue: [User]) -> String {
    queue.enumerated()
        .map { "\($0 + 1). \($1.firstName)\n" }
        .joined(separator: "")
}

print("Ready to accept commands")

while let update = bot.nextUpdateSync() {
    print("--- update: \(update)")
    
    try router.process(update: update)
}

fatalError("Server stopped due to error: \(bot.lastError.unwrapOptional)")

extension User: Equatable {
    public static func == (lhs: TelegramBotSDK.User, rhs: TelegramBotSDK.User) -> Bool {
        lhs.id == rhs.id
    }
}
