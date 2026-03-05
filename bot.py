import json
import os
import time
from typing import Any, Dict, List, Optional

import requests


TOKEN = os.environ.get("EMIAS_QUEUE_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Environment variable EMIAS_QUEUE_BOT_TOKEN is not set")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

QUEUES_FILE = "queues.json"  # thread_id -> [users]

# thread_id (str) -> message_id последнего сообщения с очередью в этом топике
LAST_QUEUE_MESSAGES: Dict[str, int] = {}


def api_call(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(BASE_URL + method, json=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok", False):
        raise RuntimeError(f"Telegram API error in {method}: {data}")
    return data


def get_updates(offset: Optional[int] = None, timeout: int = 30) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    data = api_call("getUpdates", params)
    return data.get("result", [])


def send_message(
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
    message_thread_id: Optional[int] = None,
) -> Optional[int]:
    params: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_notification": True,
    }
    if reply_to_message_id is not None:
        params["reply_to_message_id"] = reply_to_message_id
    if message_thread_id is not None:
        params["message_thread_id"] = message_thread_id
    data = api_call("sendMessage", params)
    result = data.get("result")
    if isinstance(result, dict):
        return result.get("message_id")
    return None


def send_queue_message(chat_id: int, thread_id: int, thread_key: str, text: str) -> None:
    """
    Отправляет сообщение с очередью и удаляет предыдущее сообщение очереди в этом топике.
    """
    new_id = send_message(chat_id, text, message_thread_id=thread_id)
    last_id = LAST_QUEUE_MESSAGES.get(thread_key)
    if last_id is not None and new_id is not None and last_id != new_id:
        delete_message(chat_id, last_id)
    if new_id is not None:
        LAST_QUEUE_MESSAGES[thread_key] = new_id


def delete_message(chat_id: int, message_id: int) -> None:
    try:
        api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception as e:
        # Не критично, если удалить не получилось
        print(f"Error deleting message {message_id} in chat {chat_id}: {e}")


def get_chat_admin_ids(chat_id: int) -> List[int]:
    data = api_call("getChatAdministrators", {"chat_id": chat_id})
    return [adm["user"]["id"] for adm in data.get("result", [])]


def load_queues() -> Dict[str, List[Dict[str, Any]]]:
    if not os.path.exists(QUEUES_FILE):
        return {}
    try:
        with open(QUEUES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_queues(queues: Dict[str, List[Dict[str, Any]]]) -> None:
    with open(QUEUES_FILE, "w", encoding="utf-8") as f:
        json.dump(queues, f, ensure_ascii=False, indent=2)


def format_queue(queue: List[Dict[str, Any]]) -> str:
    if not queue:
        return "Очередь пуста"
    lines = [f"{i + 1}. {u.get('first_name', '')}" for i, u in enumerate(queue)]
    return "В очереди:\n" + "\n".join(lines)


def user_in_any_queue(queues: Dict[str, List[Dict[str, Any]]], user_id: int) -> bool:
    for q in queues.values():
        if any(u.get("id") == user_id for u in q):
            return True
    return False


def user_with_username_in_any_queue(queues: Dict[str, List[Dict[str, Any]]], username: str) -> bool:
    for q in queues.values():
        if any(u.get("username") == username for u in q):
            return True
    return False


def main() -> None:
    print("Python EMIASQueueBot started")
    offset: Optional[int] = None
    queues: Dict[str, List[Dict[str, Any]]] = load_queues()

    while True:
        try:
            updates = get_updates(offset=offset, timeout=30)
        except Exception as e:
            print(f"Error in getUpdates: {e}")
            time.sleep(5)
            continue

        for upd in updates:
            offset = upd["update_id"] + 1

            message = upd.get("message")
            if not message:
                continue

            text: Optional[str] = message.get("text")
            if not text or not text.startswith("/"):
                continue

            chat = message.get("chat", {})
            chat_id = chat.get("id")
            if chat_id is None:
                continue

            thread_id = message.get("message_thread_id")
            if thread_id is None:
                # Команды имеют смысл только в топиках
                send_message(chat_id, "Необходимо выполнить команду в iOS или Android топике")
                continue

            from_user = message.get("from")
            if not from_user:
                continue

            user_id = from_user.get("id")
            first_name = from_user.get("first_name", "")
            username = from_user.get("username")
            message_id = message.get("message_id")

            # Разбор команды: /cmd или /cmd@BotName
            parts = text.split()
            cmd_full = parts[0]  # /add или /add@BotName
            cmd = cmd_full.split("@")[0][1:]

            args = parts[1:]

            thread_key = str(thread_id)
            queue = queues.setdefault(thread_key, [])

            print(f"update in thread {thread_id}, cmd={cmd}, from={user_id}")

            if cmd == "add":
                if args:
                    # /add @username — добавить в очередь по нику (для миграции, доступно всем)
                    username_to_add: Optional[str] = None
                    entities = message.get("entities") or []
                    for ent in entities:
                        if ent.get("type") == "mention":
                            offset_ent = ent.get("offset", 0)
                            length_ent = ent.get("length", 0)
                            mention_text = text[offset_ent : offset_ent + length_ent]
                            if mention_text.startswith("@"):
                                username_to_add = mention_text[1:]
                                break

                    if not username_to_add and args[0].startswith("@"):
                        username_to_add = args[0][1:]

                    if not username_to_add:
                        reply_id = send_message(
                            chat_id,
                            "Нужно указать корректный @ник: /add @username",
                            message_thread_id=thread_id,
                        )
                        if message_id is not None:
                            delete_message(chat_id, message_id)
                        if reply_id is not None:
                            time.sleep(3)
                            delete_message(chat_id, reply_id)
                        continue

                    # Не даём добавить, если этот @ник уже есть в какой-либо очереди
                    if user_with_username_in_any_queue(queues, username_to_add):
                        reply_id = send_message(
                            chat_id,
                            f"Пользователь @{username_to_add} уже в очереди",
                            message_thread_id=thread_id,
                        )
                        if message_id is not None:
                            delete_message(chat_id, message_id)
                        if reply_id is not None:
                            time.sleep(3)
                            delete_message(chat_id, reply_id)
                        continue

                    # Мы не знаем реальный id и имя, поэтому используем @ник как отображаемое имя
                    queue.append(
                        {
                            "id": None,
                            "first_name": f"@{username_to_add}",
                            "username": username_to_add,
                        }
                    )
                    save_queues(queues)
                    send_queue_message(chat_id, thread_id, thread_key, format_queue(queue))
                    if message_id is not None:
                        delete_message(chat_id, message_id)
                else:
                    # /add — добавить в очередь себя
                    if user_in_any_queue(queues, user_id):
                        # Отвечаем пользователю и затем удаляем и команду, и ответ
                        reply_id = send_message(chat_id, "Вы уже в очереди", message_thread_id=thread_id)
                        if message_id is not None:
                            delete_message(chat_id, message_id)
                        if reply_id is not None:
                            # даём время прочитать сообщение
                            time.sleep(1)
                            delete_message(chat_id, reply_id)
                        continue

                    queue.append({"id": user_id, "first_name": first_name, "username": username})
                    save_queues(queues)
                    send_queue_message(chat_id, thread_id, thread_key, format_queue(queue))
                    if message_id is not None:
                        delete_message(chat_id, message_id)

            elif cmd == "add_first":
                # Добавить себя на первую позицию в очереди текущего топика
                if user_in_any_queue(queues, user_id):
                    reply_id = send_message(chat_id, "Вы уже в очереди", message_thread_id=thread_id)
                    if message_id is not None:
                        delete_message(chat_id, message_id)
                    if reply_id is not None:
                        time.sleep(3)
                        delete_message(chat_id, reply_id)
                    continue

                queue.insert(0, {"id": user_id, "first_name": first_name, "username": username})
                save_queues(queues)
                send_queue_message(chat_id, thread_id, thread_key, format_queue(queue))
                if message_id is not None:
                    delete_message(chat_id, message_id)

            elif cmd == "list":
                send_queue_message(chat_id, thread_id, thread_key, format_queue(queue))
                if message_id is not None:
                    delete_message(chat_id, message_id)

            elif cmd == "remove":
                # Если есть @ник и отправитель админ — удаляем по нику
                if args:
                    try:
                        admin_ids = get_chat_admin_ids(chat_id)
                    except Exception as e:
                        print(f"Error in getChatAdministrators: {e}")
                        send_message(chat_id, "Не удалось получить список админов", message_thread_id=thread_id)
                        continue

                    if user_id not in admin_ids:
                        send_message(chat_id, "Удалять из очереди по @нику может только админ", message_thread_id=thread_id)
                        continue

                    # Ищем @ник в сущностях для надёжности
                    username_to_remove: Optional[str] = None
                    entities = message.get("entities") or []
                    for ent in entities:
                        if ent.get("type") == "mention":
                            offset_ent = ent.get("offset", 0)
                            length_ent = ent.get("length", 0)
                            mention_text = text[offset_ent : offset_ent + length_ent]
                            if mention_text.startswith("@"):
                                username_to_remove = mention_text[1:]
                                break

                    if not username_to_remove and args[0].startswith("@"):
                        username_to_remove = args[0][1:]

                    if not username_to_remove:
                        send_message(
                            chat_id,
                            "Нужно указать корректный @ник: /remove @username",
                            message_thread_id=thread_id,
                        )
                        continue

                    idx = next(
                        (i for i, u in enumerate(queue) if u.get("username") == username_to_remove),
                        None,
                    )
                    if idx is None:
                        send_message(
                            chat_id,
                            f"Пользователь @{username_to_remove} не найден в очереди",
                            message_thread_id=thread_id,
                        )
                        continue

                    queue.pop(idx)
                    save_queues(queues)
                    send_queue_message(chat_id, thread_id, thread_key, format_queue(queue))
                    if message_id is not None:
                        delete_message(chat_id, message_id)
                else:
                    # Без аргументов — пользователь удаляет только себя из очереди текущего топика
                    idx = next((i for i, u in enumerate(queue) if u.get("id") == user_id), None)
                    if idx is None:
                        send_message(chat_id, "Вы не в очереди", message_thread_id=thread_id)
                        continue

                    queue.pop(idx)
                    save_queues(queues)
                    send_queue_message(chat_id, thread_id, thread_key, format_queue(queue))
                    if message_id is not None:
                        delete_message(chat_id, message_id)

            elif cmd == "clear":
                try:
                    admin_ids = get_chat_admin_ids(chat_id)
                except Exception as e:
                    print(f"Error in getChatAdministrators: {e}")
                    send_message(chat_id, "Не удалось получить список админов", message_thread_id=thread_id)
                    continue

                if user_id not in admin_ids:
                    send_message(chat_id, "Очищать очередь может только админ", message_thread_id=thread_id)
                    continue

                queues[thread_key] = []
                save_queues(queues)
                # Показываем пустую очередь и удаляем старое сообщение с очередью
                send_queue_message(chat_id, thread_id, thread_key, format_queue(queues[thread_key]))
                if message_id is not None:
                    delete_message(chat_id, message_id)

            else:
                # Неизвестная команда — игнорируем или можно ответить help'ом
                continue


if __name__ == "__main__":
    main()

