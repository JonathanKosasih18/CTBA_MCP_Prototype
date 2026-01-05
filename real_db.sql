SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+07:00";

-- --------------------------------------------------------

-- Table structure for table `users`
CREATE TABLE `users` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `username` varchar(255) NOT NULL,
    `name` varchar(255) NOT NULL,
    `telepon` varchar(255) DEFAULT NULL,
    `email` varchar(255) NOT NULL,
    `api_token` varchar(255) NOT NULL,
    `email_verified_at` timestamp NULL DEFAULT NULL,
    `password` varchar(255) NOT NULL,
    `remember_token` varchar(100) DEFAULT NULL,
    `dev_id` varchar(255) DEFAULT NULL,
    `master_dev_id` varchar(255) DEFAULT NULL,
    `super_dev_id` varchar(255) DEFAULT NULL,
    `virtual_dev_id` varchar(255) DEFAULT NULL,
    `ver` varchar(30) DEFAULT NULL,
    `image_t` varchar(255) DEFAULT NULL,
    `level` varchar(255) DEFAULT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL,
    `deleted_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Table structure for table `customers`
CREATE TABLE `customers` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `custcode` varchar(255) DEFAULT NULL,
    `custname` varchar(255) NOT NULL,
    `birthdate` date DEFAULT NULL,
    `religion` varchar(255) DEFAULT NULL,
    `specialist` varchar(255) DEFAULT NULL,
    `clasification` varchar(255) DEFAULT NULL,
    `phone` varchar(255) DEFAULT NULL,
    `email` varchar(255) DEFAULT NULL,
    `instagram` varchar(255) DEFAULT NULL,
    `facebook` varchar(255) DEFAULT NULL,
    `pic` varchar(255) DEFAULT NULL,
    `dccode` varchar(255) DEFAULT NULL,
    `amcode` varchar(255) DEFAULT NULL,
    `tscode` varchar(255) DEFAULT NULL,
    `pscode` varchar(255) DEFAULT NULL,
    `nsmcode` varchar(255) DEFAULT NULL,
    `status` varchar(255) DEFAULT '1',
    `top` varchar(255) DEFAULT NULL,
    `university` varchar(255) DEFAULT NULL,
    `teach` varchar(3) DEFAULT 'No',
    `avg_turnover` int(11) DEFAULT NULL,
    `daya_beli` int(11) DEFAULT NULL,
    `tempat_praktek` int(11) DEFAULT NULL,
    `jumlah_pasien` int(11) DEFAULT NULL,
    `jumlah_pasien_ortho` int(11) DEFAULT 0,
    `usia_pasien` int(11) DEFAULT NULL,
    `potensi_total` int(11) DEFAULT 0,
    `biaya_konvensional` varchar(255) DEFAULT '0',
    `biaya_self_ligating` varchar(255) DEFAULT '0',
    `ppdgs` varchar(255) DEFAULT NULL,
    `kepribadian_dokter` varchar(255) DEFAULT NULL,
    `fokus_dokter` varchar(255) DEFAULT NULL,
    `segmentasi_ortho` varchar(255) DEFAULT NULL,
    `grup_dokter` varchar(255) DEFAULT NULL,
    `service` varchar(255) DEFAULT NULL,
    `biaya_konvensional_aesthetic` varchar(255) DEFAULT NULL,
    `biaya_self_ligating_aesthetic` varchar(255) DEFAULT NULL,
    `biaya_tambalan` int(11) DEFAULT 0,
    `pengerjaan_ortho` varchar(255) DEFAULT NULL,
    `target_ormco` varchar(255) DEFAULT NULL,
    `target_sunmed` varchar(255) DEFAULT NULL,
    `target_produk_lain` varchar(255) DEFAULT NULL,
    `produk_kompetitor_ortho` varchar(255) DEFAULT NULL,
    `produk_kompetitor_resto` varchar(255) DEFAULT NULL,
    `info_terkait_dokter` varchar(2000) DEFAULT NULL,
    `feedback_produk_ortho` varchar(2000) DEFAULT NULL,
    `feedback_produk_resto` varchar(2000) DEFAULT NULL,
    `invisalign_provider` varchar(255) DEFAULT NULL,
    `tier_invisalign_provider` varchar(255) DEFAULT NULL,
    `target_visit_per_bulan` int(11) DEFAULT NULL,
    `perlu_diketahui_dokter` varchar(255) DEFAULT NULL,
    `perlu_diinfo_dokter` varchar(255) DEFAULT NULL,
    `objektif` text DEFAULT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL,
    `deleted_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Table structure for table `clinics`
CREATE TABLE `clinics` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `cliniccode` varchar(255) DEFAULT NULL,
    `clinicname` varchar(255) NOT NULL,
    `address` varchar(255) DEFAULT NULL,
    `citycode` varchar(255) DEFAULT NULL,
    `provcode` varchar(255) DEFAULT NULL,
    `locality` varchar(255) DEFAULT NULL,
    `postalcode` varchar(255) DEFAULT NULL,
    `phone` varchar(255) DEFAULT NULL,
    `latitude` varchar(255) DEFAULT NULL,
    `longitude` varchar(255) DEFAULT NULL,
    `custcode` varchar(255) NOT NULL,
    `purchasing` varchar(255) DEFAULT NULL,
    `purchasingnumber` varchar(255) DEFAULT NULL,
    `payment` varchar(255) DEFAULT NULL,
    `paymentnumber` varchar(255) DEFAULT NULL,
    `status` int(11) NOT NULL DEFAULT 1,
    `status_klinik` varchar(255) DEFAULT NULL,
    `jumlah_dental_chair` int(12) DEFAULT NULL,
    `jumlah_pasien_per_hari` int(12) DEFAULT NULL,
    `jumlah_pasien_pasang_ortho_baru` int(12) DEFAULT NULL,
    `jumlah_drg_parktek` int(12) DEFAULT NULL,
    `dokter_lain_diklinik` varchar(2000) DEFAULT NULL,
    `mesin_klinik` varchar(255) DEFAULT NULL,
    `jadwal_praktek` varchar(255) DEFAULT NULL,
    `waktu_kunjungan` time DEFAULT NULL,
    `deleted_at` timestamp NULL DEFAULT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Table structure for table `products`
CREATE TABLE `products` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `prodname` varchar(255) NOT NULL,
    `catcode` bigint(20) UNSIGNED NOT NULL,
    `status` int(11) NOT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Table structure for table `plans`
CREATE TABLE `plans` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `userid` bigint(20) UNSIGNED NOT NULL,
    `custcode` bigint(20) UNSIGNED NOT NULL,
    `cliniccode` bigint(20) UNSIGNED NOT NULL,
    `date` date NOT NULL,
    `time` time NOT NULL,
    `plan` varchar(255) NOT NULL,
    `productcode` bigint(20) NOT NULL,
    `plantype` varchar(255) NOT NULL,
    `status` int(11) NOT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Table structure for table `reports`
CREATE TABLE `reports` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `reportdate` datetime NOT NULL,
    `date` date NOT NULL,
    `time` time NOT NULL,
    `visitnote` varchar(2000) DEFAULT NULL,
    `amount_po` int(11) DEFAULT NULL,
    `po_pic` varchar(255) DEFAULT NULL,
    `idplan` bigint(20) UNSIGNED NOT NULL,
    `latitude` varchar(255) DEFAULT NULL,
    `longitude` varchar(255) DEFAULT NULL,
    `pcompbrand` varchar(255) DEFAULT NULL,
    `pcomptype` varchar(255) DEFAULT NULL,
    `pcompqty` varchar(255) DEFAULT NULL,
    `checkinselfi` varchar(255) DEFAULT NULL,
    `selfi` varchar(255) DEFAULT NULL,
    `status` int(11) DEFAULT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

-- Table structure for table `transactions`
CREATE TABLE `transactions` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `inv_number` varchar(255) NOT NULL,
    `inv_date` date NOT NULL,
    `qty` int(11) NOT NULL,
    `unit` varchar(255) DEFAULT NULL,
    `amount` int(11) NOT NULL,
    `salesman_name` varchar(255) NOT NULL,
    `cust_id` varchar(255) NOT NULL,
    `item_id` varchar(255) NOT NULL,
    `product` text DEFAULT NULL,
    `target_product` varchar(255) DEFAULT NULL,
    `brand_product` varchar(255) DEFAULT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL,
    `deleted_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

