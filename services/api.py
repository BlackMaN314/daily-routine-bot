import aiohttp
from aiohttp import ClientConnectorError, ClientError, ClientTimeout
import asyncio
import hmac
import hashlib
import time
import logging
from typing import Optional, Dict, Any, List
from config import BACKEND_URL, BACKEND_USER_ID, BACKEND_ACCESS_TOKEN, WEB_APP_URL, BOT_TOKEN
from services.token_storage import token_storage

logger = logging.getLogger(__name__)


class API:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_id = BACKEND_USER_ID
        self.access_token = BACKEND_ACCESS_TOKEN
        
        if not self.base_url:
            self.base_url = "http://localhost:8000"

    async def _get_session(self, telegram_id: Optional[int] = None, force_new: bool = False, 
                          access_token: Optional[str] = None) -> aiohttp.ClientSession:
        should_recreate = (
            force_new or 
            self.session is None or 
            self.session.closed or
            (access_token is not None and self.session is not None and not self.session.closed)
        )
        
        if should_recreate:
            if self.session and not self.session.closed:
                await self.session.close()
            
            headers = {}
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
            elif self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    def _generate_telegram_hash(self, data: Dict[str, str]) -> str:
        if not BOT_TOKEN:
            raise Exception("BOT_TOKEN не задан для генерации hash")
        
        data_copy = {}
        for k, v in data.items():
            if k != "hash" and v is not None and str(v) != "":
                data_copy[k] = str(v)
        
        keys = sorted(data_copy.keys())
        data_string = "\n".join(f"{k}={data_copy[k]}" for k in keys)
        secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
        h = hmac.new(secret_key, data_string.encode(), hashlib.sha256)
        return h.hexdigest()
    
    async def register_telegram_user(self, telegram_id: int, username: Optional[str] = None, 
                                     first_name: Optional[str] = None, last_name: Optional[str] = None,
                                     photo_url: Optional[str] = None) -> Dict[str, Any]:
        telegram_data = {
            "id": str(telegram_id),
            "auth_date": str(int(time.time())),
        }
        
        if username:
            telegram_data["username"] = username
        if first_name:
            telegram_data["first_name"] = first_name
        if last_name:
            telegram_data["last_name"] = last_name
        if photo_url:
            telegram_data["photo_url"] = photo_url
        
        telegram_data["hash"] = self._generate_telegram_hash(telegram_data)
        
        url = f"{self.base_url}/login/telegram"
        session = aiohttp.ClientSession()
        
        try:
            async with session.post(url, json=telegram_data) as response:
                if response.status == 401:
                    error_text = await response.text()
                    raise Exception(f"Ошибка авторизации: неверные данные Telegram. Ответ сервера: {error_text}")
                response.raise_for_status()
                auth_response = await response.json()
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Не удалось подключиться к серверу {self.base_url} при регистрации: {e}")
            raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при регистрации: {e}")
            raise Exception(f"Ошибка сети при регистрации: {e}")
        except Exception as e:
            if "Ошибка" in str(e):
                raise
            raise Exception(f"Ошибка API при регистрации: {e}")
        finally:
            await session.close()
        
        user = auth_response.get("user", {})
        tokens = auth_response.get("tokens", {})
        
        user_id = user.get("id")
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        
        logger.info(f"Регистрация пользователя: telegram_id={telegram_id}, user_id={user_id}")
        
        return {
            "user": {
                "id": user_id,
                "telegram_id": telegram_id
            },
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        }
    
    async def _refresh_access_token(self, telegram_id: int) -> Optional[str]:
        try:
            refresh_token = await token_storage.get_refresh_token(telegram_id)
            if not refresh_token:
                return None
            
            url = f"{self.base_url}/auth/getaccesstoken"
            session = aiohttp.ClientSession()
            
            try:
                async with session.post(url, json={"refresh_token": refresh_token}) as response:
                    if response.status == 401:
                        return None
                    response.raise_for_status()
                    data = await response.json()
                    new_access_token = data.get("access_token")
                    if new_access_token:
                        await token_storage.update_access_token(telegram_id, new_access_token)
                    return new_access_token
            finally:
                await session.close()
        except Exception as e:
            logger.error(f"Ошибка при обновлении access token для telegram_id={telegram_id}: {e}", exc_info=True)
            return None
    
    async def _refresh_token_pair(self, telegram_id: int) -> Optional[Dict[str, str]]:
        """Обновить пару токенов через refresh_token"""
        try:
            refresh_token = await token_storage.get_refresh_token(telegram_id)
            if not refresh_token:
                return None
            
            url = f"{self.base_url}/auth/getrefreshtoken"
            session = aiohttp.ClientSession()
            
            try:
                async with session.post(url, json={"refresh_token": refresh_token}) as response:
                    if response.status == 401:
                        return None
                    response.raise_for_status()
                    data = await response.json()
                    new_access_token = data.get("access_token")
                    new_refresh_token = data.get("refresh_token")
                    if new_access_token and new_refresh_token:
                        await token_storage.update_tokens(telegram_id, new_access_token, new_refresh_token)
                        logger.info(f"Пара токенов обновлена для пользователя {telegram_id}")
                    return {"access_token": new_access_token, "refresh_token": new_refresh_token}
            finally:
                await session.close()
        except Exception as e:
            logger.warning(f"Ошибка при обновлении пары токенов: {e}")
            return None
    
    async def _get_user_token(self, telegram_id: int, username: Optional[str] = None,
                              first_name: Optional[str] = None, last_name: Optional[str] = None,
                              photo_url: Optional[str] = None) -> Optional[str]:
        access_token = await token_storage.get_access_token(telegram_id)
        if access_token:
            return access_token
        try:
            auth_data = await self.register_telegram_user(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                photo_url=photo_url
            )
            tokens = auth_data.get("tokens", {})
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            user_id = auth_data.get("user", {}).get("id")
            
            if access_token and refresh_token:
                await token_storage.save_tokens(
                    telegram_id=telegram_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
            else:
                logger.error(f"Токены не получены при регистрации для telegram_id={telegram_id}")
                return None
            
            return access_token
        except Exception as e:
            logger.error(f"Ошибка при регистрации пользователя {telegram_id}: {e}", exc_info=True)
            return None

    async def check_connection(self) -> bool:
        try:
            session = aiohttp.ClientSession()
            try:
                async with session.get(f"{self.base_url}/users", timeout=ClientTimeout(total=5)) as response:
                    return True
            except asyncio.TimeoutError:
                logger.error(f"Таймаут при подключении к {self.base_url}")
                return False
            except ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к {self.base_url}: {e}")
                return False
            finally:
                await session.close()
        except Exception as e:
            logger.error(f"Ошибка при проверке подключения: {e}")
            return False

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        return await self._get(path, params)

    async def post(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        return await self._post(path, data)

    async def put(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        return await self._put(path, data)

    async def delete(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        return await self._delete(path, params)

    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        telegram_id = params.get("telegram_id") if params else None
        username = params.get("username")
        first_name = params.get("first_name")
        last_name = params.get("last_name")
        photo_url = params.get("photo_url")
        
        access_token = None
        user_id = self.user_id
        
        if telegram_id:
            access_token = await token_storage.get_access_token(telegram_id)
            user_id = await token_storage.get_user_id(telegram_id)
            
            logger.debug(f"Получен токен из хранилища для telegram_id={telegram_id}: {'есть' if access_token else 'нет'}")
            
            if not access_token:
                logger.info(f"Токен не найден в хранилище для telegram_id={telegram_id}, регистрируем пользователя")
                access_token = await self._get_user_token(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
                if not access_token:
                    raise Exception("Не удалось получить токен. Попробуйте отправить /start")
                user_id = await token_storage.get_user_id(telegram_id)
                if not user_id:
                    raise Exception("Не удалось получить user_id при регистрации. Попробуйте отправить /start")
                logger.info(f"Пользователь зарегистрирован, токен получен для telegram_id={telegram_id}")
        
        if not access_token and self.access_token:
            access_token = self.access_token
            logger.debug("Используется токен из конфигурации")
        
        if not access_token:
            logger.error(f"Токен не доступен для запроса {path}, telegram_id={telegram_id}")
            raise Exception("Токен не доступен. Попробуйте отправить /start для регистрации")

        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        
        if not access_token:
            logger.warning(f"Токен не получен для telegram_id={telegram_id}, user_id={user_id}")
            if telegram_id:
                raise Exception("Токен не доступен. Попробуйте отправить /start для регистрации")
            else:
                raise Exception("Токен не доступен")
        
        logger.debug(f"Используется токен для запроса {path}, telegram_id={telegram_id}")
        session = await self._get_session(access_token=access_token)

        if path == "/habits/today":
            url = f"{self.base_url}/habits"
            try:
                async with session.get(url) as response:
                    if response.status == 401:
                        if telegram_id:
                            logger.warning(f"Получен 401 для telegram_id={telegram_id}, пытаемся обновить токен")
                            new_token = await self._refresh_access_token(telegram_id)
                            if not new_token:
                                logger.info(f"Refresh token истек, перерегистрируем пользователя telegram_id={telegram_id}")
                                new_token = await self._get_user_token(
                                    telegram_id=telegram_id,
                                    username=username,
                                    first_name=first_name,
                                    last_name=last_name,
                                    photo_url=photo_url
                                )
                            if new_token:
                                logger.info(f"Токен обновлен для telegram_id={telegram_id}, повторяем запрос")
                                await session.close()
                                session = await self._get_session(access_token=new_token)
                                async with session.get(url) as retry_response:
                                    if retry_response.status == 401:
                                        raise Exception("Токен недействителен даже после обновления. Попробуйте отправить /start")
                                    retry_response.raise_for_status()
                                    habits = await retry_response.json()
                            else:
                                raise Exception("Токен истёк, не удалось обновить. Попробуйте отправить /start")
                        else:
                            raise Exception("Ошибка авторизации (401). Попробуйте отправить /start для регистрации")
                    else:
                        response.raise_for_status()
                        habits = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            if not isinstance(habits, list):
                logger.warning(f"Ожидался массив привычек, получен: {type(habits)}")
                habits = []
            
            mapped_habits = [self._map_habit_from_backend(h) for h in habits]
            return {"habits": mapped_habits}

        if path.startswith("/habits/") and not path.endswith("/stats") and not path.endswith("/history"):
            parts = path.split("/")
            if len(parts) >= 3 and parts[2].isdigit():
                habit_id = parts[2]
                url = f"{self.base_url}/habits/{habit_id}"
                try:
                    async with session.get(url) as response:
                        if response.status == 404:
                            raise Exception("Привычка не найдена")
                        if response.status == 401 and telegram_id:
                            new_token = await self._refresh_access_token(telegram_id)
                            if not new_token:
                                new_token = await self._get_user_token(
                                    telegram_id=telegram_id,
                                    username=username,
                                    first_name=first_name,
                                    last_name=last_name,
                                    photo_url=photo_url
                                )
                            if not new_token:
                                raise Exception("Токен истёк, требуется повторная регистрация")
                            await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.get(url) as retry_response:
                                if retry_response.status == 404:
                                    raise Exception("Привычка не найдена")
                                retry_response.raise_for_status()
                                habit = await retry_response.json()
                        else:
                            response.raise_for_status()
                            habit = await response.json()
                except aiohttp.ClientError as e:
                    raise Exception(f"Ошибка сети: {e}")
                except Exception as e:
                    raise Exception(f"Ошибка API: {e}")

                return {"habit": self._map_habit_from_backend(habit)}

        if path.startswith("/habits/") and path.endswith("/stats"):
            parts = path.split("/")
            habit_id = int(parts[2])
            period = params.get("period", "week") if params else "week"
            return await self._habit_stats(user_id, habit_id, period, telegram_id)

        if path.startswith("/habits/") and path.endswith("/history"):
            parts = path.split("/")
            habit_id = int(parts[2])
            period = params.get("period", "week") if params else "week"
            return await self._habit_history(user_id, habit_id, period, telegram_id)

        if path == "/habits/progress":
            period = params.get("period", "week") if params else "week"
            if not user_id and telegram_id:
                user_id = await token_storage.get_user_id(telegram_id)
            return await self._progress(user_id, period, telegram_id, username, first_name, last_name, photo_url)

        if path == "/telegram/settings":
            url = f"{self.base_url}/user/me/settings"
            try:
                async with session.get(url) as response:
                    if response.status == 404:
                        create_url = f"{self.base_url}/user/me/settings"
                        async with session.put(create_url, json={}) as create_response:
                            if create_response.status in [200, 201]:
                                settings = await create_response.json()
                            else:
                                settings = {
                                    "user_id": user_id,
                                    "timezone": "Europe/Moscow",
                                    "do_not_disturb": False,
                                    "notify_times": ["08:00"]
                                }
                    elif response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if not new_token:
                            raise Exception("Токен истёк, автоматическое обновление не удалось. Попробуйте отправить /start")
                        await session.close()
                        session = await self._get_session(access_token=new_token)
                            async with session.get(url) as retry_response:
                                if retry_response.status == 404:
                                    create_url = f"{self.base_url}/user/me/settings"
                                async with session.put(create_url, json={}) as create_response:
                                    if create_response.status in [200, 201]:
                                        settings = await create_response.json()
                                    else:
                                        settings = {
                                            "user_id": user_id,
                                            "timezone": "Europe/Moscow",
                                            "do_not_disturb": False,
                                            "notify_times": ["08:00"]
                                        }
                            else:
                                retry_response.raise_for_status()
                                settings = await retry_response.json()
                    else:
                        response.raise_for_status()
                        settings = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            return {"settings": self._map_settings_from_backend(settings)}

        if path == "/telegram/users/check":
            telegram_id = params.get("telegram_id") if params else None
            if telegram_id:
                try:
                    access_token = await token_storage.get_access_token(telegram_id)
                    if access_token:
                        check_session = await self._get_session(access_token=access_token)
                        check_url = f"{self.base_url}/user/me"
                        async with check_session.get(check_url) as check_response:
                            if check_response.status == 200:
                                return {"exists": True}
                            elif check_response.status == 401:
                                new_token = await self._refresh_access_token(telegram_id)
                                if new_token:
                                    check_session = await self._get_session(access_token=new_token)
                                    async with check_session.get(check_url) as retry_response:
                                        if retry_response.status == 200:
                                            return {"exists": True}
                except Exception as e:
                    logger.debug(f"Ошибка при проверке пользователя telegram_id={telegram_id}: {e}")
            return {"exists": False}

        if path == "/telegram/registration-link":
            return {"url": f"{WEB_APP_URL}/register"}

        if path == "/telegram/auth-link":
            return {"url": f"{WEB_APP_URL}/dashboard"}

        url = f"{self.base_url}{path}"
        try:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка сети: {e}")
        except Exception as e:
            raise Exception(f"Ошибка API: {e}")

    async def _post(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        telegram_id = data.get("telegram_id") if data else None
        username = data.get("username")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        photo_url = data.get("photo_url")
        
        access_token = None
        user_id = self.user_id
        
        if telegram_id:
            access_token = await token_storage.get_access_token(telegram_id)
            user_id = await token_storage.get_user_id(telegram_id)
            
            if not access_token:
                access_token = await self._get_user_token(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
                if not access_token:
                    raise Exception("Не удалось получить токен. Попробуйте отправить /start")
                user_id = await token_storage.get_user_id(telegram_id)
                if not user_id:
                    raise Exception("Не удалось получить user_id при регистрации. Попробуйте отправить /start")
        
        if not access_token and self.access_token:
            access_token = self.access_token
        
        if not access_token:
            raise Exception("Токен не доступен")

        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        
        session = await self._get_session(access_token=access_token)

        if path == "/habits/complete":
            if not data:
                raise Exception("habit_id обязателен")
            habit_id = data.get("habit_id")
            if not habit_id:
                raise Exception("habit_id обязателен")

            url = f"{self.base_url}/habits/{habit_id}"
            payload = {"is_done": True}

            try:
                async with session.patch(url, json=payload) as response:
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.patch(url, json=payload) as retry_response:
                                retry_response.raise_for_status()
                                habit = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                    else:
                        response.raise_for_status()
                        habit = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            mapped = self._map_habit_from_backend(habit)
            return {"habit": mapped, "streak": mapped.get("streak", 0)}

        if path == "/habits/undo":
            if not data:
                raise Exception("habit_id обязателен")
            habit_id = data.get("habit_id")
            if not habit_id:
                raise Exception("habit_id обязателен")

            url = f"{self.base_url}/habits/{habit_id}"
            payload = {
                "is_done": False,
            }

            try:
                async with session.patch(url, json=payload) as response:
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.patch(url, json=payload) as retry_response:
                                retry_response.raise_for_status()
                                habit = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                    else:
                        response.raise_for_status()
                        habit = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            mapped = self._map_habit_from_backend(habit)
            return {"habit": mapped, "streak": mapped.get("streak", 0)}

        if path == "/habits/create":
            if not data:
                raise Exception("Данные привычки обязательны")
            
            title = data.get("title")
            habit_type = data.get("type", "count")
            value = data.get("value", 1)
            unit = data.get("unit", "")
            is_active = data.get("is_active", True)
            is_beneficial = data.get("is_beneficial", True)
            
            if not title:
                raise Exception("Название привычки обязательно")
            
            backend_format = "time" if habit_type == "time" else "count"
            backend_habit_type = "beneficial" if is_beneficial else "harmful"
            
            payload = {
                "title": title,
                "format": backend_format,
                "value": int(value),
                "is_active": is_active,
                "type": backend_habit_type
            }
            
            if unit:
                payload["unit"] = unit
            
            url = f"{self.base_url}/habits"
            try:
                logger.debug(f"Отправка запроса на создание привычки: {url}, payload: {payload}")
                async with session.post(url, json=payload) as response:
                    if response.status == 400:
                        error_text = await response.text()
                        logger.error(f"Ошибка 400 при создании привычки: {error_text}, payload: {payload}")
                        raise Exception(f"Ошибка валидации: {error_text}")
                    
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.post(url, json=payload) as retry_response:
                                retry_response.raise_for_status()
                                habit = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, требуется повторная регистрация")
                    else:
                        response.raise_for_status()
                        habit = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                if hasattr(e, 'status') and hasattr(e, 'message'):
                    error_detail = f"Status: {e.status}, Message: {e.message}"
                    if hasattr(e, 'request_info'):
                        error_detail += f", URL: {e.request_info.url}"
                    raise Exception(f"Ошибка сети: {error_detail}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")
            
            return {"habit": self._map_habit_from_backend(habit)}

        url = f"{self.base_url}{path}"
        try:
            async with session.post(url, json=data) as response:
                if response.status == 401 and telegram_id:
                    new_token = await self._get_user_token(
                        telegram_id=telegram_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        photo_url=photo_url
                    )
                    if new_token:
                        if session and not session.closed:
                            await session.close()
                        session = await self._get_session(access_token=new_token)
                        async with session.post(url, json=data) as retry_response:
                            retry_response.raise_for_status()
                            return await retry_response.json()
                    else:
                        raise Exception("Токен истёк, требуется повторная регистрация")
                else:
                        response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка сети: {e}")
        except Exception as e:
            raise Exception(f"Ошибка API: {e}")

    async def _put(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        telegram_id = data.get("telegram_id") if data else None
        username = data.get("username")
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        photo_url = data.get("photo_url")
        
        access_token = None
        user_id = self.user_id
        
        if telegram_id:
            access_token = await token_storage.get_access_token(telegram_id)
            user_id = await token_storage.get_user_id(telegram_id)
            
            if not access_token:
                access_token = await self._get_user_token(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
                if not access_token:
                    raise Exception("Не удалось получить токен. Попробуйте отправить /start")
                user_id = await token_storage.get_user_id(telegram_id)
                if not user_id:
                    raise Exception("Не удалось получить user_id при регистрации. Попробуйте отправить /start")
        
        if not access_token and self.access_token:
            access_token = self.access_token
        
        if not access_token:
            raise Exception("Токен не доступен")

        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        
        session = await self._get_session(access_token=access_token)

        if path == "/telegram/settings/reminders":
            if not data:
                raise Exception("enabled обязателен")
            enabled = data.get("enabled", True)
            payload = {"do_not_disturb": not enabled}

            url = f"{self.base_url}/user/me/settings"
            try:
                async with session.patch(url, json=payload) as response:
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.patch(url, json=payload) as retry_response:
                                retry_response.raise_for_status()
                                settings = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                    else:
                        response.raise_for_status()
                        settings = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            return {"success": True, "settings": self._map_settings_from_backend(settings)}

        if path == "/telegram/settings/morning-time":
            if not data:
                raise Exception("time обязателен")
            time_str = data.get("time")
            if not time_str:
                raise Exception("time обязателен")

            settings_url = f"{self.base_url}/user/me/settings"
            try:
                async with session.get(settings_url) as response:
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.get(settings_url) as retry_response:
                                retry_response.raise_for_status()
                                current_settings = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                    else:
                        response.raise_for_status()
                        current_settings = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            notify_times: List[str] = current_settings.get("notify_times") or []
            if time_str not in notify_times:
                notify_times.append(time_str)

            payload = {
                "notify_times": notify_times,
            }

            url = settings_url
            try:
                async with session.patch(url, json=payload) as response:
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.patch(url, json=payload) as retry_response:
                                retry_response.raise_for_status()
                                settings = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                    else:
                        response.raise_for_status()
                        settings = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            return {"success": True, "settings": self._map_settings_from_backend(settings)}

        if path == "/telegram/settings/notify-times":
            if not data:
                raise Exception("notify_times обязателен")
            notify_times = data.get("notify_times")
            if notify_times is None:
                raise Exception("notify_times обязателен")

            payload = {
                "notify_times": notify_times,
            }

            url = f"{self.base_url}/user/me/settings"
            try:
                async with session.patch(url, json=payload) as response:
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.patch(url, json=payload) as retry_response:
                                retry_response.raise_for_status()
                                settings = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                    else:
                        response.raise_for_status()
                        settings = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            return {"success": True, "settings": self._map_settings_from_backend(settings)}

        if path == "/telegram/settings/dnd":
            enabled = data.get("enabled", False) if data else False

            payload = {
                "do_not_disturb": enabled,
            }

            url = f"{self.base_url}/user/me/settings"
            try:
                async with session.patch(url, json=payload) as response:
                    if response.status == 401 and telegram_id:
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            if session and not session.closed:
                                await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.patch(url, json=payload) as retry_response:
                                retry_response.raise_for_status()
                                settings = await retry_response.json()
                        else:
                            raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                    else:
                        response.raise_for_status()
                        settings = await response.json()
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Не удалось подключиться к серверу {self.base_url}: {e}")
                raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при запросе к {self.base_url}: {e}")
                raise Exception(f"Ошибка сети: {e}")
            except Exception as e:
                logger.error(f"Ошибка API: {e}")
                raise Exception(f"Ошибка API: {e}")

            return {"success": True, "settings": self._map_settings_from_backend(settings)}
        
        url = f"{self.base_url}{path}"
        try:
            async with session.put(url, json=data) as response:
                if response.status == 401 and telegram_id:
                    new_token = await self._refresh_access_token(telegram_id)
                    if not new_token:
                        new_token = await self._get_user_token(
                            telegram_id=telegram_id,
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            photo_url=photo_url
                        )
                    if new_token:
                        await session.close()
                        session = await self._get_session(access_token=new_token)
                        async with session.put(url, json=data) as retry_response:
                            retry_response.raise_for_status()
                            return await retry_response.json()
                    else:
                        raise Exception("Токен истёк, автоматическая перерегистрация не удалась. Попробуйте отправить /start")
                else:
                        response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка сети: {e}")
        except Exception as e:
            raise Exception(f"Ошибка API: {e}")

    @staticmethod
    def _map_habit_from_backend(h: Dict[str, Any]) -> Dict[str, Any]:
        if not h:
            return {}

        habit_type = h.get("type", "count")
        bot_type = "quantity" if habit_type in ("time", "count") else "boolean"

        value = h.get("value", 0) or 0
        is_done = h.get("is_done", False)
        unit = h.get("unit") or ""
        
        backend_progress = h.get("progress") or h.get("current_value") or (value if is_done else 0)
        
        display_value = value
        display_progress = backend_progress
        display_unit = unit
        if unit == "минут" and value >= 60 and value % 60 == 0:
            display_value = value / 60
            display_progress = backend_progress / 60
            display_unit = "часов"

        return {
            "id": h.get("id"),
            "name": h.get("title", "Привычка"),
            "emoji": "📌",
            "progress": display_progress,
            "goal": display_value,
            "unit": display_unit,
            "completed": is_done,
            "type": bot_type,
            "streak": h.get("series", 0),
            "reminder_settings": {
                "enabled": True,
                "time": "18:00",
                "days": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
            },
        }

    @staticmethod
    def _map_settings_from_backend(s: Dict[str, Any]) -> Dict[str, Any]:
        if not s:
            return {
                "reminders_enabled": True,
                "morning_time": "08:00",
                "dnd_enabled": False,
                "dnd_start": "22:00",
                "dnd_end": "08:00",
                "timezone": "UTC",
            }

        notify_times: List[str] = s.get("notify_times") or []
        morning_time = notify_times[0] if notify_times else "08:00"

        dnd = s.get("do_not_disturb", False)
        timezone = s.get("timezone", "UTC")

        return {
            "reminders_enabled": not dnd,
            "morning_time": morning_time,
            "notify_times": notify_times,
            "dnd_enabled": dnd,
            "dnd_start": "22:00",
            "dnd_end": "08:00",
            "timezone": timezone,
        }

    async def _habit_stats(self, user_id: str, habit_id: int, period: str, telegram_id: Optional[int] = None) -> Dict[str, Any]:
        username = None
        first_name = None
        last_name = None
        photo_url = None
        
        access_token = None
        
        if telegram_id:
            access_token = await token_storage.get_access_token(telegram_id)
            
            if not access_token:
                access_token = await self._get_user_token(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
                if not access_token:
                    raise Exception("Не удалось получить токен. Попробуйте отправить /start")
        
        if not access_token and self.access_token:
            access_token = self.access_token
        
        if not access_token:
            raise Exception("Токен не доступен")

        session = await self._get_session(access_token=access_token)
        url = f"{self.base_url}/habits/{habit_id}"

        try:
            async with session.get(url) as response:
                if response.status == 401 and telegram_id:
                    new_token = await self._refresh_access_token(telegram_id)
                    if not new_token:
                        new_token = await self._get_user_token(
                            telegram_id=telegram_id,
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            photo_url=photo_url
                        )
                    if new_token:
                        await session.close()
                        session = await self._get_session(access_token=new_token)
                        async with session.get(url) as retry_response:
                            retry_response.raise_for_status()
                            habit = await retry_response.json()
                    else:
                        raise Exception("Токен истёк, требуется повторная регистрация")
                else:
                    response.raise_for_status()
                    habit = await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка сети: {e}")
        except Exception as e:
            raise Exception(f"Ошибка API: {e}")

        mapped = self._map_habit_from_backend(habit)

        total_days = 7 if period == "week" else 30
        completed = mapped.get("streak", 0)
        completed = min(completed, total_days)

        return {
            "habit": {
                "id": mapped.get("id"),
                "name": mapped.get("name"),
                "emoji": mapped.get("emoji", "📌"),
            },
            "stats": {
                "completed": completed,
                "total": total_days,
                "current_streak": mapped.get("streak", 0),
                "best_streak": mapped.get("streak", 0),
                "last_completed": "ранее",
                "avg_frequency": round(completed / total_days * 7, 1) if total_days else 0,
            },
        }

    async def _habit_history(self, user_id: str, habit_id: int, period: str, telegram_id: Optional[int] = None) -> Dict[str, Any]:
        from datetime import datetime, timedelta

        username = None
        first_name = None
        last_name = None
        photo_url = None
        access_token = None
        
        if telegram_id:
            access_token = await token_storage.get_access_token(telegram_id)
            
            if not access_token:
                access_token = await self._get_user_token(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
                if not access_token:
                    raise Exception("Не удалось получить токен. Попробуйте отправить /start")
        
        if not access_token and self.access_token:
            access_token = self.access_token
        
        if not access_token:
            raise Exception("Токен не доступен")

        session = await self._get_session(access_token=access_token)
        url = f"{self.base_url}/habits/{habit_id}"

        try:
            async with session.get(url) as response:
                if response.status == 401 and telegram_id:
                    new_token = await self._refresh_access_token(telegram_id)
                    if not new_token:
                        new_token = await self._get_user_token(
                            telegram_id=telegram_id,
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            photo_url=photo_url
                        )
                    if new_token:
                        await session.close()
                        session = await self._get_session(access_token=new_token)
                        async with session.get(url) as retry_response:
                            retry_response.raise_for_status()
                            habit = await retry_response.json()
                    else:
                        raise Exception("Токен истёк, требуется повторная регистрация")
                else:
                    response.raise_for_status()
                    habit = await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка сети: {e}")
        except Exception as e:
            raise Exception(f"Ошибка API: {e}")

        mapped = self._map_habit_from_backend(habit)

        days_count = 7 if period == "week" else 30
        today = datetime.now()
        history = []

        for i in range(days_count):
            date = today - timedelta(days=i)
            date_str = date.strftime("%d.%m.%Y")
            completed = (i % 3) != 0
            amount = mapped.get("goal", 0) if completed else 0

            history.append(
                {
                    "date": date_str,
                    "completed": completed,
                    "amount": amount,
                }
            )

        return {
            "habit": {
                "id": mapped.get("id"),
                "name": mapped.get("name"),
                "emoji": mapped.get("emoji", "📌"),
                "unit": mapped.get("unit", ""),
            },
            "history": history,
        }

    async def _progress(self, user_id: Optional[str], period: str, telegram_id: Optional[int] = None,
                      username: Optional[str] = None, first_name: Optional[str] = None,
                      last_name: Optional[str] = None, photo_url: Optional[str] = None) -> Dict[str, Any]:
        access_token = None
        
        if telegram_id:
            access_token = await token_storage.get_access_token(telegram_id)
            
            if not user_id:
                stored_user_id = await token_storage.get_user_id(telegram_id)
                if stored_user_id:
                    user_id = str(stored_user_id)
            
            if not access_token:
                logger.info(f"Токен не найден для telegram_id={telegram_id}, регистрируем пользователя")
                access_token = await self._get_user_token(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
                if not access_token:
                    raise Exception("Не удалось получить токен. Попробуйте отправить /start")
                stored_user_id = await token_storage.get_user_id(telegram_id)
                if stored_user_id:
                    user_id = str(stored_user_id)
                logger.info(f"Пользователь зарегистрирован, user_id={user_id}, telegram_id={telegram_id}")
        
        if not access_token and self.access_token:
            access_token = self.access_token
        
        if not access_token:
            raise Exception("Токен не доступен. Попробуйте отправить /start для регистрации")

        session = await self._get_session(access_token=access_token)
        url = f"{self.base_url}/habits"

        try:
            async with session.get(url) as response:
                if response.status == 401:
                    if telegram_id:
                        logger.warning(f"Получен 401 при запросе прогресса для telegram_id={telegram_id}, обновляем токен")
                        new_token = await self._refresh_access_token(telegram_id)
                        if not new_token:
                            logger.info(f"Refresh token истек или не получен, перерегистрируем пользователя telegram_id={telegram_id}")
                            new_token = await self._get_user_token(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name,
                                last_name=last_name,
                                photo_url=photo_url
                            )
                        if new_token:
                            logger.info(f"Токен обновлен для telegram_id={telegram_id}, повторяем запрос прогресса")
                            await session.close()
                            session = await self._get_session(access_token=new_token)
                            async with session.get(url) as retry_response:
                                if retry_response.status == 401:
                                    logger.error(f"Токен все еще недействителен после обновления для telegram_id={telegram_id}")
                                    raise Exception("Токен недействителен даже после обновления. Попробуйте отправить /start")
                                retry_response.raise_for_status()
                                habits = await retry_response.json()
                        else:
                            logger.error(f"Не удалось обновить токен для telegram_id={telegram_id}")
                            raise Exception("Токен истёк, не удалось обновить. Попробуйте отправить /start")
                    else:
                        logger.error("Получен 401 без telegram_id при запросе прогресса")
                        raise Exception("Ошибка авторизации (401). Попробуйте отправить /start для регистрации")
                else:
                    response.raise_for_status()
                    habits = await response.json()
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Не удалось подключиться к серверу {self.base_url} при запросе прогресса: {e}")
            raise Exception(f"Не удалось подключиться к серверу. Проверь, что бэкенд запущен на {self.base_url}")
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при запросе прогресса к {self.base_url}: {e}")
            raise Exception(f"Ошибка сети: {e}")
        except Exception as e:
            logger.error(f"Ошибка API при запросе прогресса: {e}")
            raise Exception(f"Ошибка API: {e}")

        mapped_habits = [self._map_habit_from_backend(h) for h in habits]

        total_days = 1 if period == "today" else (7 if period == "week" else 30)

        habits_progress = []
        total_completed = 0
        total_habits = 0
        best_streak = None
        max_streak = 0

        for habit in mapped_habits:
            streak = habit.get("streak", 0)
            completed = min(streak, total_days)
            total = total_days

            habits_progress.append(
                {
                    "id": habit.get("id"),
                    "name": habit.get("name"),
                    "emoji": habit.get("emoji", "📌"),
                    "completed": completed,
                    "total": total,
                }
            )

            total_completed += completed
            total_habits += total

            if streak > max_streak:
                max_streak = streak
                best_streak = {
                    "name": habit.get("name"),
                    "days": streak,
                }

        return {
            "habits": habits_progress,
            "total": {
                "completed": total_completed,
                "total": total_habits,
            },
            "best_streak": best_streak or {"name": "Нет данных", "days": 0},
        }
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _delete(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        telegram_id = params.get("telegram_id") if params else None
        username = params.get("username")
        first_name = params.get("first_name")
        last_name = params.get("last_name")
        photo_url = params.get("photo_url")
        
        access_token = None
        user_id = self.user_id
        
        if telegram_id:
            access_token = await token_storage.get_access_token(telegram_id)
            user_id = await token_storage.get_user_id(telegram_id)
            
            if not access_token:
                access_token = await self._get_user_token(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    photo_url=photo_url
                )
                if not access_token:
                    raise Exception("Не удалось получить токен. Попробуйте отправить /start")
                user_id = await token_storage.get_user_id(telegram_id)
                if not user_id:
                    raise Exception("Не удалось получить user_id при регистрации. Попробуйте отправить /start")
        
        if not access_token and self.access_token:
            access_token = self.access_token
        
        if not access_token:
            raise Exception("Токен не доступен")

        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        
        session = await self._get_session(access_token=access_token)
        
        if path.startswith("/habits/delete/"):
            parts = path.split("/")
            if len(parts) >= 4 and parts[3].isdigit():
                habit_id = parts[3]
                url = f"{self.base_url}/habits/{habit_id}"
                try:
                    async with session.delete(url) as response:
                        if response.status == 401 and telegram_id:
                            new_token = await self._refresh_access_token(telegram_id)
                            if not new_token:
                                new_token = await self._get_user_token(
                                    telegram_id=telegram_id,
                                    username=username,
                                    first_name=first_name,
                                    last_name=last_name,
                                    photo_url=photo_url
                                )
                            if new_token:
                                await session.close()
                                session = await self._get_session(access_token=new_token)
                                async with session.delete(url) as retry_response:
                                    retry_response.raise_for_status()
                                    return await retry_response.json()
                            else:
                                raise Exception("Токен истёк, требуется повторная регистрация")
                        else:
                            response.raise_for_status()
                            return await response.json()
                except aiohttp.ClientError as e:
                    raise Exception(f"Ошибка сети: {e}")
                except Exception as e:
                    raise Exception(f"Ошибка API: {e}")
        
        url = f"{self.base_url}{path}"
        try:
            async with session.delete(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка сети: {e}")
        except Exception as e:
            raise Exception(f"Ошибка API: {e}")


api = API(BACKEND_URL)
