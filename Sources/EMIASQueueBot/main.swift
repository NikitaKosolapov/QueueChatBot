import Foundation
import TelegramBotSDK

let token = readToken(from: "EMIAS_QUEUE_BOT_TOKEN")
let bot = TelegramBot(token: token)
let router = Router(bot: bot)

struct Queue {
    var queue: [String: Int] = [:]
    var order = 1
    let topic: Int
}

var iosQueue = Queue(topic: 2)
var androidQueue = Queue(topic: 3)

let errorText = "Необходимо выполнить команду в iOS или Android топике"
let startText = "Сначала запустите бота"

var isStart = false

// Обработчик команды /start
router["start"] = { context in
    guard !isStart else {
        reply(with: context, text: "Бот уже запущен")
        return true
    }
    
    isStart = true
    reply(with: context, text: "Привет! Я бот для управления очередью")
    return true
}

// Обработчик команды /stop
router["stop"] = { context in
    guard isStart else {
        reply(with: context, text: "Бот не запущен")
        return true
    }
    
    isStart = false
    reply(with: context, text: "Бот остановлен")
    return false
}

// Обработчик команды /help
router["help"] = { context in
    let helpText = """
    Доступные команды:
    
    /start - Начать использование бота
    /stop - Остановить бот
    /add - Добавить себя в очередь
    /list - Показать очередь
    /remove - Удалить себя из очереди
    /clear - Очистить очередь
    
    *\(errorText)

    """
    
    context.respondAsync(helpText)
    return true
}


// Обработчик команды /add
router["add"] = { context in
    guard isStart else {
        reply(with: context, text: startText)
        return true
    }
    
    guard let username = context.update.message?.from?.firstName else { return true }
    
    guard iosQueue.queue[username] == nil || androidQueue.queue[username] == nil else {
        reply(with: context, text: "Вы уже в очереди")
        return false
    }
    
    var maxNumber: Int = 0
    var responseText: String = ""
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        maxNumber = iosQueue.queue.values.max() ?? 0
        iosQueue.queue[username] = maxNumber + 1
        
        for (name, number) in iosQueue.queue {
            responseText += "\(number). \(name)\n"
        }
    case androidQueue.topic:
        maxNumber = androidQueue.queue.values.max() ?? 0
        androidQueue.queue[username] = maxNumber + 1
        
        for (name, number) in androidQueue.queue {
            responseText += "\(number). \(name)\n"
        }
    default:
        reply(with: context, text: errorText)
        return true
    }
    
    reply(with: context, text: responseText)

    return true
}

// Обработчик команды /list
router["list"] = { context in
    guard isStart else {
        reply(with: context, text: startText)
        return true
    }
    
    var responseText: String
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        responseText = iosQueue.queue.isEmpty ? "Очередь пуста" : "В очереди:\n"
        
        for (name, number) in iosQueue.queue {
            responseText += "\(number). \(name)\n"
        }
    case androidQueue.topic:
        responseText = androidQueue.queue.isEmpty ? "Очередь пуста" : "В очереди:\n"
        
        for (name, number) in androidQueue.queue {
            responseText += "\(number). \(name)\n"
        }
    default:
        reply(with: context, text: errorText)
        return true
    }
    
    reply(with: context, text: responseText)
    return true
}

// Обработчик команды /remove
router["remove"] = { context in
    guard isStart else {
        reply(with: context, text: startText)
        return true
    }
    
    guard let username = context.update.message?.from?.firstName else { return true }
    
    guard iosQueue.queue[username] != nil || androidQueue.queue[username] != nil else {
        reply(with: context, text: "Вы не в очереди")
        return false
    }
    
    var responseText: String = ""
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        iosQueue.queue.removeValue(forKey: username)
        // После удаления пересчитываем порядковые номера
        let sortedDevelopers = iosQueue.queue.sorted(by: { $0.value < $1.value })
        iosQueue.queue = Dictionary(uniqueKeysWithValues: sortedDevelopers.enumerated().map { ($1.key, $0 + 1) })
        
        for (name, number) in iosQueue.queue {
            responseText += "\(number). \(name)\n"
        }
    case androidQueue.topic:
        androidQueue.queue.removeValue(forKey: username)
        // После удаления пересчитываем порядковые номера
        let sortedDevelopers = androidQueue.queue.sorted(by: { $0.value < $1.value })
        androidQueue.queue = Dictionary(uniqueKeysWithValues: sortedDevelopers.enumerated().map { ($1.key, $0 + 1) })
        
        for (name, number) in androidQueue.queue {
            responseText += "\(number). \(name)\n"
        }
    default:
        reply(with: context, text: errorText)
        return true
    }
    
    reply(with: context, text: responseText)
    
    return true
}

router["clear"] = { context in
    guard let admins = bot.getChatAdministratorsSync(chatId: .chat(context.chatId ?? 0)),
          let username = context.message?.from?.username,
            admins.map({ $0.user.username }).contains(username) else {
        reply(with: context, text: "Очищать очередь может только админ")
        return true
    }
    
    guard isStart else {
        reply(with: context, text: startText)
        return true
    }
    
    switch context.update.message?.replyToMessage?.messageId {
    case iosQueue.topic:
        iosQueue.queue = [:]
    case androidQueue.topic:
        androidQueue.queue = [:]
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

print("Ready to accept commands")

while let update = bot.nextUpdateSync() {
    print("--- update: \(update)")

    try router.process(update: update)
}

fatalError("Server stopped due to error: \(bot.lastError.unwrapOptional)")
