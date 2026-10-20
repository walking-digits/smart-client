import Link from "next/link";

export default function Header() {
  return (
    <header
      className="w-full p-3 pr-4 pl-4 rounded-2xl flex justify-between bg-mist-200 dark:bg-mist-900"
    >
      <nav
        className="w-full flex gap-4 justify-center"
      >
        <Link
          href="/"
          className="block after:block after:h-px after:w-0 hover:after:w-full after:bg-foreground after:transition-all"
        >
          Главная
        </Link>
        |
        <Link
          href="/loans"
          className="block after:block after:h-px after:w-0 hover:after:w-full after:bg-foreground after:transition-all"
        >
          Категории кредитов
        </Link>
        |
        <Link
          href="/contacts"
          className="block after:block after:h-px after:w-0 hover:after:w-full after:bg-foreground after:transition-all"
        >
          Контакты
        </Link>
      </nav>
      <div
        className="flex gap-4"
      >
        <Link
          href="/register"
          className="block after:block after:h-px after:w-0 hover:after:w-full after:bg-foreground after:transition-all"
        >
          Регистрация
        </Link>
        |
        <Link
          href="/login"
          className="block after:block after:h-px after:w-0 hover:after:w-full after:bg-foreground after:transition-all"
        >
          Вход
        </Link>
      </div>
    </header>
  );
}
