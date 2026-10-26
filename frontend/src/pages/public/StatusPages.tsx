import { Link } from "react-router-dom";

import { useAppSelector } from "../../app/hooks";
import { homePathFor, selectUser } from "../../features/auth/authSlice";

function StatusPage({ code, title, body }: { code: string; title: string; body: string }) {
  const user = useAppSelector(selectUser);
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 text-center">
      <p className="text-6xl font-bold text-brand-600">{code}</p>
      <h1 className="mt-4 text-2xl font-bold">{title}</h1>
      <p className="mt-2 max-w-md text-slate-500">{body}</p>
      <Link to={user ? homePathFor(user.role) : "/"} className="btn-primary mt-6">
        {user ? "Back to my dashboard" : "Go home"}
      </Link>
    </div>
  );
}

export function Forbidden() {
  return <StatusPage code="403" title="You don't have access to this page" body="This area belongs to a different kind of account. Sign in with the right role to see it." />;
}

export function NotFound() {
  return <StatusPage code="404" title="Page not found" body="The page you're looking for doesn't exist or was moved." />;
}
