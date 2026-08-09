/* ============================================
   ZRaurora 个人主页脚本
   ============================================ */

(function() {
    'use strict';

    // ==========================================
    // 导航栏滚动效果
    // ==========================================
    const navbar = document.getElementById('navbar');
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('section[id]');

    function handleScroll() {
        // 导航栏背景
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }

        // 激活导航项
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop - 100;
            const sectionHeight = section.offsetHeight;
            if (window.scrollY >= sectionTop && window.scrollY < sectionTop + sectionHeight) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === '#' + current) {
                link.classList.add('active');
            }
        });

        // 回到顶部按钮
        const backToTop = document.getElementById('backToTop');
        if (window.scrollY > 500) {
            backToTop.classList.add('show');
        } else {
            backToTop.classList.remove('show');
        }
    }

    window.addEventListener('scroll', handleScroll, { passive: true });

    // ==========================================
    // 移动端菜单
    // ==========================================
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');

    navToggle.addEventListener('click', () => {
        navToggle.classList.toggle('active');
        navMenu.classList.toggle('active');
    });

    // 点击导航链接后关闭菜单
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navToggle.classList.remove('active');
            navMenu.classList.remove('active');
        });
    });

    // ==========================================
    // 回到顶部
    // ==========================================
    const backToTop = document.getElementById('backToTop');
    backToTop.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });

    // ==========================================
    // 复制功能
    // ==========================================
    const copyToast = document.getElementById('copyToast');
    let toastTimer = null;

    window.copyText = function(elementId) {
        const element = document.getElementById(elementId);
        const text = element.textContent;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                showToast();
            }).catch(() => {
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    };

    function fallbackCopy(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            showToast();
        } catch (e) {
            console.error('复制失败:', e);
        }
        document.body.removeChild(textarea);
    }

    function showToast() {
        copyToast.classList.add('show');
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            copyToast.classList.remove('show');
        }, 2000);
    }

    // ==========================================
    // 粒子背景效果
    // ==========================================
    function createParticles() {
        const container = document.getElementById('particles');
        if (!container) return;

        const particleCount = 30;

        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            
            // 随机位置
            particle.style.left = Math.random() * 100 + '%';
            particle.style.top = Math.random() * 100 + '%';
            
            // 随机大小
            const size = Math.random() * 4 + 2;
            particle.style.width = size + 'px';
            particle.style.height = size + 'px';
            
            // 随机动画延迟和持续时间
            particle.style.animationDelay = Math.random() * 15 + 's';
            particle.style.animationDuration = (Math.random() * 10 + 10) + 's';
            
            // 随机颜色
            const colors = ['#6366f1', '#8b5cf6', '#10b981', '#f59e0b'];
            particle.style.background = colors[Math.floor(Math.random() * colors.length)];
            
            container.appendChild(particle);
        }
    }

    createParticles();

    // ==========================================
    // 滚动动画（元素进入视口时显示）
    // ==========================================
    function initScrollAnimations() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                    observer.unobserve(entry.target);
                }
            });
        }, observerOptions);

        // 观察需要动画的元素
        const animateElements = document.querySelectorAll(
            '.server-card, .download-card, .stats-card, .section-header'
        );

        animateElements.forEach((el, index) => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(30px)';
            el.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.6s ease ${index * 0.1}s`;
            observer.observe(el);
        });
    }

    // 等页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initScrollAnimations);
    } else {
        initScrollAnimations();
    }

    // ==========================================
    // 服务器状态模拟（演示用）
    // ==========================================
    function simulateServerStatus() {
        // 这里可以替换为真实的服务器状态查询
        // 目前只是演示效果
        const statusElements = document.querySelectorAll('.status-text');
        statusElements.forEach(el => {
            if (el.textContent === '在线运行中' || el.textContent === '在线') {
                // 随机波动在线人数
                const onlineEl = el.closest('.server-detail')?.querySelector('.highlight');
                if (onlineEl && onlineEl.textContent.includes('/')) {
                    // 保持不变，演示用
                }
            }
        });
    }

    // 每30秒更新一次（演示用）
    setInterval(simulateServerStatus, 30000);

    // ==========================================
    // 平滑滚动增强
    // ==========================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                const offsetTop = target.offsetTop - 64; // 减去导航栏高度
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });

    // ==========================================
    // 控制台彩蛋
    // ==========================================
    console.log('%c⛏️ ZRaurora瑞不卷', 'font-size: 24px; font-weight: bold; color: #6366f1;');
    console.log('%c欢迎来到我的个人主页！', 'font-size: 14px; color: #94a3b8;');
    console.log('%c拒绝内卷，享受生活 ✨', 'font-size: 12px; color: #10b981;');
    console.log('');

})();
