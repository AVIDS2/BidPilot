import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";

export function Nav() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const [lastScrollY, setLastScrollY] = useState(0);
  const location = useLocation();

  // 全屏设计页面不显示导航栏（落地页、登录、注册）
  const hideOnRoutes = ["/", "/login", "/signup"];
  const shouldHide = hideOnRoutes.includes(location.pathname);

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      setIsScrolled(currentScrollY > 50);
      setIsHidden(currentScrollY > lastScrollY && currentScrollY > 100);
      setLastScrollY(currentScrollY);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [lastScrollY]);

  if (shouldHide) return null;

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        isScrolled
          ? "bg-[#0a0a0a]/80 backdrop-blur-md"
          : "bg-transparent"
      } ${isHidden ? "-translate-y-full" : "translate-y-0"}`}
    >
      <div className="flex justify-between items-center px-8 py-6 max-w-7xl mx-auto">
        {/* Logo */}
        <Link
          to="/"
          className="text-2xl font-medium tracking-[-0.04em] text-white hover:text-[#84cc16] transition-colors duration-300"
        >
          DocPilot
        </Link>

        {/* 导航链接 */}
        <div className="flex items-center gap-8">
          <Link
            to="/"
            className="text-sm text-[#a3a3a3] hover:text-[#84cc16] transition-colors duration-300"
          >
            首页
          </Link>
          <Link
            to="/pricing"
            className="text-sm text-[#a3a3a3] hover:text-[#84cc16] transition-colors duration-300"
          >
            定价
          </Link>
          <Link
            to="/docs"
            className="text-sm text-[#a3a3a3] hover:text-[#84cc16] transition-colors duration-300"
          >
            文档
          </Link>
          <Link
            to="/login"
            className="text-sm text-[#a3a3a3] hover:text-[#84cc16] transition-colors duration-300"
          >
            登录
          </Link>
          <Link
            to="/signup"
            className="inline-flex items-center text-sm font-medium px-5 py-2.5 bg-[#84cc16] text-[#0a0a0a] hover:bg-[#65a30d] transition-all duration-300 hover:scale-[0.98]"
          >
            注册
          </Link>
        </div>
      </div>
    </nav>
  );
}
