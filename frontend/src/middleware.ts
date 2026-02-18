import { type NextRequest } from "next/server";
import { createMiddlewareClient } from "@/lib/supabase-middleware";

// Routes that don't require authentication
const PUBLIC_ROUTES = ["/login"];

export async function middleware(request: NextRequest) {
  const { supabase, supabaseResponse } = createMiddlewareClient(request);

  // Refresh the session (important for token refresh)
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;

  // Allow public routes
  if (PUBLIC_ROUTES.some((route) => pathname.startsWith(route))) {
    // If user is already logged in, redirect to dashboard
    if (user) {
      const url = request.nextUrl.clone();
      url.pathname = "/chat";
      return Response.redirect(url);
    }
    return supabaseResponse;
  }

  // Protect all other routes - redirect to login if not authenticated
  if (!user) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return Response.redirect(url);
  }

  return supabaseResponse;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     * - public folder files
     * - API routes (handled by Python backend auth)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$|api/).*)",
  ],
};
