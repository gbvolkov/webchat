const en = {
  language: {
    label: 'Language',
    english: 'English',
    russian: 'Russian',
  },
  app: {
    status: {
      checkingSession: 'Checking your session...',
      preparingSignIn: 'Preparing sign-in screen...',
      welcomeBack: 'Welcome back, {name}!',
    },
  },
  common: {
    actions: {
      search: 'Search',
      reset: 'Reset',
      delete: 'Delete',
      cancel: 'Cancel',
    },
    confirmations: {
      deleteChat: {
        title: 'Delete chat?',
        description: 'The chat will be hidden from history.',
        confirm: 'Delete',
        cancel: 'Cancel',
      },
    },
  },
  menu: {
    items: {
      newChat: 'New chat',
      chatSearch: 'Chat search',
      chatHistory: 'History',
      chatLibrary: 'Library',
    },
    signOut: 'Sign out',
    needsAuth: 'Please sign in to start a new chat.',
    errors: {
      create: 'Failed to create a new chat.',
      delete: 'Failed to delete chat.',
    },
    success: {
      delete: 'Chat deleted',
    },
  },
  chat: {
    input: {
      placeholder: 'Type a message...',
      attachments: 'Files',
    },
    errors: {
      stream: 'Error, please try again.',
    unauthorized: 'Unable to determine the current user. Please sign in again.',
    },
  },
  threads: {
    untitled: 'New chat',
    fallbackTitle: 'Thread {id}',
    deleteTooltip: 'Delete chat',
    actions: {
      openMenu: 'More actions',
      exportPdf: 'Export as PDF',
      exportMarkdown: 'Export as Markdown',
      exportDocx: 'Export as DOCX',
      delete: 'Delete chat',
    },
    notifications: {
      exportSuccess: 'Export started',
      exportFailed: 'Failed to export chat',
    },
  },
  pages: {
    chat: {
      errors: {
        loadModels: 'Failed to load the list of models.',
      },
      placeholder: 'Hello, {name}! Choose a chat from the list or create a new one to start talking.',
    },
    chatDetail: {
      modelLabel: 'Model',
      placeholders: {
        loading: 'Loading chat history...',
        loadError: 'Unable to load messages. Please refresh the page.',
        empty: 'Hello, {name}! Ask a question and the assistant will continue the conversation.',
      },
      errors: {
        fallbackModels: 'The provider did not return models. Using the fallback list.',
        loadModels: 'Failed to load the list of models.',
        updateModel: 'Failed to save the selected model.',
      },
    },
    chatSearch: {
      title: 'Chat search',
      subtitle: 'Find conversations by keyword. Apply a model filter if you specify one.',
      phraseLabel: 'Phrase',
      phrasePlaceholder: 'Enter a keyword',
      modelLabel: 'Model',
      modelPlaceholder: 'All models',
      results: {
        title: 'Results',
        loading: 'Searching...',
        empty: 'Nothing found. Try adjusting the query.',
        metrics: {
          bestSimilarity: 'Best similarity: {value}',
          similarityThreshold: 'Threshold (distance × 1.25): {value}',
          minSimilarity: 'Minimum similarity: {value}',
          bestDistance: 'Best distance: {value}',
          distanceThreshold: 'Distance threshold: {value}',
        },
        card: {
          untitled: 'Untitled',
          model: 'Model: {label}',
          modelUnknown: 'not specified',
          similarity: 'Similarity: {value}',
          delete: 'Delete',
        },
      },
      notifications: {
        phraseRequired: 'Enter a phrase to search',
        searchFailed: 'Failed to perform search.',
        deleteSuccess: 'Chat deleted',
        deleteFailed: 'Failed to delete chat.',
      },
    },
    chatsHistory: {
      title: 'Chat history',
      subtitle: 'Browse your conversation archive by topic.',
      searchPlaceholder: 'Search',
      emptyTab: 'In the future, content will appear here...',
      tabs: {
        all: 'All chats',
        documents: 'Documents and reports',
        creative: 'Creative processes',
        products: 'Products',
      },
      card: {
        export: 'Export',
        delete: 'Delete',
      },
    },
    chatLibrary: {
      placeholder: 'The tasks library will appear here.',
    },
    auth: {
      titles: {
        login: 'Sign in',
        register: 'Create account',
      },
      subtitles: {
        hasAccount: 'Already have an account?',
        needsAccount: 'Need an account?',
        signIn: 'Sign in',
        createOne: 'Create one',
      },
      fields: {
        username: 'Username',
        password: 'Password',
        confirmPassword: 'Confirm password',
        fullName: 'Full name (optional)',
        email: 'Email (optional)',
      },
      submit: {
        login: 'Sign in',
        loginInProgress: 'Signing in...',
        register: 'Create account',
        registerInProgress: 'Creating account...',
      },
      feedback: {
        passwordsMismatch: 'Passwords do not match.',
        accountCreated: 'Account created successfully. Signing you in...',
        createFailed: 'Unable to create the account. Please try again.',
        loginFailed: 'Unable to sign in. Please check your credentials and try again.',
      },
    },
  },
} as const

export default en



