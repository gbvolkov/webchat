const ru = {
  language: {
    label: 'Язык',
    english: 'Английский',
    russian: 'Русский',
  },
  app: {
    status: {
      checkingSession: 'Проверяем вашу сессию...',
      preparingSignIn: 'Готовим экран входа...',
      welcomeBack: 'С возвращением, {name}!',
    },
  },
  common: {
    actions: {
      search: 'Найти',
      reset: 'Сбросить',
      delete: 'Удалить',
      cancel: 'Отмена',
    },
    confirmations: {
      deleteChat: {
        title: 'Удалить чат?',
        description: 'Чат будет скрыт из списка истории.',
        confirm: 'Удалить',
        cancel: 'Отмена',
      },
    },
  },
  menu: {
    items: {
      newChat: 'Новый чат',
      chatSearch: 'Поиск по чатам',
      chatHistory: 'История',
      chatLibrary: 'Библиотека',
    },
    signOut: 'Выйти',
    needsAuth: 'Войдите, чтобы начать новый чат.',
    errors: {
      create: 'Не удалось создать новый чат.',
      delete: 'Не удалось удалить чат.',
    },
    success: {
      delete: 'Чат удалён.',
    },
  },
  chat: {
    input: {
      placeholder: 'Напишите сообщение...',
      attachments: 'Файлы',
    },
    errors: {
      stream: 'Ошибка, попробуйте ещё раз.',
    unauthorized: 'Не удалось определить пользователя. Войдите заново.',
    },
  },
  threads: {
    untitled: 'Новый чат',
    fallbackTitle: 'Тред {id}',
    deleteTooltip: 'Удалить чат',
  },
  pages: {
    chat: {
      errors: {
        loadModels: 'Не удалось загрузить список моделей.',
      },
      placeholder: 'Привет, {name}! Выберите чат из списка слева или создайте новый, чтобы начать беседу.',
    },
    chatDetail: {
      modelLabel: 'Модель',
      placeholders: {
        loading: 'Загружаем историю диалога...',
        loadError: 'Не удалось загрузить сообщения. Попробуйте перезагрузить страницу.',
        empty: 'Привет, {name}! Задайте вопрос, и ассистент продолжит разговор.',
      },
      errors: {
        fallbackModels: 'Провайдер не вернул список моделей. Используем запасной список.',
        loadModels: 'Не удалось загрузить список моделей.',
        updateModel: 'Не удалось сохранить выбранную модель.',
      },
    },
    chatSearch: {
      title: 'Поиск по чатам',
      subtitle: 'Найдите диалоги по ключевой фразе. Фильтр по модели применится, если указать её в списке.',
      phraseLabel: 'Фраза',
      phrasePlaceholder: 'Введите ключевое слово',
      modelLabel: 'Модель',
      modelPlaceholder: 'Все модели',
      results: {
        title: 'Результаты',
        loading: 'Выполняем поиск...',
        empty: 'Ничего не найдено. Попробуйте уточнить запрос.',
        metrics: {
          bestSimilarity: 'Лучшая схожесть: {value}',
          similarityThreshold: 'Порог (distance × 1.25): {value}',
          minSimilarity: 'Минимальная схожесть: {value}',
          bestDistance: 'Лучшая distance: {value}',
          distanceThreshold: 'Порог distance: {value}',
        },
        card: {
          untitled: 'Без названия',
          model: 'Модель: {label}',
          modelUnknown: 'не указана',
          similarity: 'Схожесть: {value}',
          delete: 'Удалить',
        },
      },
      notifications: {
        phraseRequired: 'Введите фразу для поиска.',
        searchFailed: 'Не удалось выполнить поиск.',
        deleteSuccess: 'Чат удалён.',
        deleteFailed: 'Не удалось удалить чат.',
      },
    },
    chatsHistory: {
      title: 'История чатов',
      subtitle: 'Изучайте вашу историю диалогов по категориям.',
      searchPlaceholder: 'Поиск',
      emptyTab: 'В будущем здесь будет контент...',
      tabs: {
        all: 'Все чаты',
        documents: 'Документы и отчёты',
        creative: 'Креативные процессы',
        products: 'Продукты',
      },
      card: {
        export: 'Экспорт',
        delete: 'Удалить',
      },
    },
    chatLibrary: {
      placeholder: 'Здесь будет библиотека задач.',
    },
    auth: {
      titles: {
        login: 'Войти',
        register: 'Создать аккаунт',
      },
      subtitles: {
        hasAccount: 'Уже есть аккаунт?',
        needsAccount: 'Нужен аккаунт?',
        signIn: 'Войти',
        createOne: 'Создать',
      },
      fields: {
        username: 'Имя пользователя',
        password: 'Пароль',
        confirmPassword: 'Подтвердите пароль',
        fullName: 'Полное имя (необязательно)',
        email: 'Email (необязательно)',
      },
      submit: {
        login: 'Войти',
        loginInProgress: 'Выполняем вход...',
        register: 'Создать аккаунт',
        registerInProgress: 'Создаём аккаунт...',
      },
      feedback: {
        passwordsMismatch: 'Пароли не совпадают.',
        accountCreated: 'Аккаунт успешно создан. Выполняем вход...',
        createFailed: 'Не удалось создать аккаунт. Попробуйте ещё раз.',
        loginFailed: 'Не удалось войти. Проверьте данные и повторите попытку.',
      },
    },
  },
} as const

export default ru


