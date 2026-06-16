// 统一只写一次页面加载监听，合并所有交互
document.addEventListener('DOMContentLoaded', function() {
    // ========== 欢迎页 - 火漆印章 & 进入按钮 ==========
    const waxSeal = document.getElementById('waxSeal');
    const letter = document.getElementById('letter');
    const enterBtn = document.getElementById('enterBtn');

    if (waxSeal && letter) {
        waxSeal.addEventListener('click', function() {
            letter.classList.remove('hidden');
        });
    }

    if (enterBtn) {
        enterBtn.addEventListener('click', function() {
            window.location.href = '/choose_role';
        });
    }

    // ========== 角色选择页 - 性别、角色切换 ==========
    const femaleBtn = document.getElementById('femaleBtn');
    const maleBtn = document.getElementById('maleBtn');
    const femaleRoles = document.getElementById('femaleRoles');
    const maleRoles = document.getElementById('maleRoles');
    const genderInput = document.getElementById('genderInput');
    const roleInput = document.getElementById('roleInput');
    const roleCards = document.querySelectorAll('.role-card');

    // 性别切换
    if (femaleBtn && maleBtn && femaleRoles && maleRoles) {
        femaleBtn.addEventListener('click', function() {
            femaleBtn.classList.add('selected');
            maleBtn.classList.remove('selected');
            femaleRoles.classList.remove('hidden');
            maleRoles.classList.add('hidden');
            genderInput.value = 'female';

            const firstRole = document.querySelector('#femaleRoles .role-card');
            if (firstRole) {
                roleCards.forEach(c => c.classList.remove('selected'));
                firstRole.classList.add('selected');
                roleInput.value = firstRole.dataset.role;
            }
        });

        maleBtn.addEventListener('click', function() {
            maleBtn.classList.add('selected');
            femaleBtn.classList.remove('selected');
            maleRoles.classList.remove('hidden');
            femaleRoles.classList.add('hidden');
            genderInput.value = 'male';

            const firstRole = document.querySelector('#maleRoles .role-card');
            if (firstRole) {
                roleCards.forEach(c => c.classList.remove('selected'));
                firstRole.classList.add('selected');
                roleInput.value = firstRole.dataset.role;
            }
        });
    }

    // 角色卡片点击
    if (roleCards.length > 0) {
        roleCards.forEach(card => {
            card.addEventListener('click', function() {
                roleCards.forEach(c => c.classList.remove('selected'));
                this.classList.add('selected');
                roleInput.value = this.dataset.role;
            });
        });
    }
});