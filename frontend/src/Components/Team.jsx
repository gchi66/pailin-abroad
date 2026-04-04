import React from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import "../Styles/Team.css";

const teamMembers = [
  {
    name: "CARISSA",
    location: {
      en: "Co-Founder & Head of Content",
      th: "ผู้ร่วมก่อตั้ง และหัวหน้าฝ่ายเนื้อหา"
    },
    image: "/images/carissa.webp",
    description: {
      en: "Hey everyone! I grew up in Los Angeles, but moved to Thailand when I was just 23 years old. I started out teaching 2nd grade in Chaiyaphum, where I became friends with my co-founder, Grant. After 6 months there, I spent 7 amazing years in Chiang Mai. Learning Thai changed everything for me - it helped me see exactly where Thai people get stuck learning English, and why. I helped create Pailin Abroad to build confidence in learners, and to make lessons from native English speakers accessible to everyone, everywhere.",
      th: "สวัสดีทุกคน! ฉันเติบโตที่ลอสแอนเจลิส แต่ย้ายมาเมืองไทยตอนอายุเพียง 23 ปี ฉันเริ่มต้นจากการสอนนักเรียนชั้น ป.2 ที่ชัยภูมิ ซึ่งเป็นที่ที่ฉันได้รู้จักกับ Grant ผู้ร่วมก่อตั้งของเรา หลังจากอยู่ที่นั่น 6 เดือน ฉันก็ไปใช้ชีวิตต่อที่เชียงใหม่อีก 7 ปีที่แสนยอดเยี่ยม การได้เรียนภาษาไทยเปลี่ยนทุกอย่างสำหรับฉัน เพราะมันทำให้ฉันเห็นชัดเลยว่าคนไทยมักติดตรงไหนเวลาเรียนภาษาอังกฤษ และเพราะอะไร ฉันร่วมสร้าง Pailin Abroad ขึ้นมาเพื่อช่วยสร้างความมั่นใจให้ผู้เรียน และเพื่อทำให้บทเรียนจากเจ้าของภาษาอังกฤษเข้าถึงได้สำหรับทุกคน ไม่ว่าจะอยู่ที่ไหนก็ตาม"
    }
  },
  {
    name: "GRANT",
    location: {
      en: "Co-Founder & Lead Developer",
      th: "ผู้ร่วมก่อตั้ง และหัวหน้าฝ่ายพัฒนา"
    },
    image: "/images/grant.webp",
    description: {
      en: "Hi! I'm Grant. I'm originally from Texas, but after I graduated from University I went over to Thailand to teach English. I was a teacher for almost 4 years in Thailand, and for 4 more years after that in China. After that I pivoted to coding and website development. While I was in Thailand, I met my co-founder, Carissa in rural Chaiyaphum. Thai people are so warm and welcoming and they helped me a lot in my journey of learning Thai, and I hope that Pailin Abroad will help them!",
      th: "สวัสดีครับ! ผมชื่อ Grant เดิมผมมาจากรัฐเท็กซัส แต่หลังจากเรียนจบมหาวิทยาลัย ผมก็เดินทางมาที่ประเทศไทยเพื่อสอนภาษาอังกฤษ ผมเป็นครูอยู่ในไทยเกือบ 4 ปี และหลังจากนั้นอีก 4 ปีในประเทศจีน ต่อมาผมก็เปลี่ยนสายมาทำงานด้านโค้ดและพัฒนาเว็บไซต์ ตอนที่อยู่เมืองไทย ผมได้เจอกับ Carissa ผู้ร่วมก่อตั้งของเรา ที่ชัยภูมิซึ่งเป็นเมืองชนบท คนไทยอบอุ่นและเป็นมิตรมาก และพวกเขาก็ช่วยผมมากในเส้นทางการเรียนภาษาไทยของผม ผมหวังว่า Pailin Abroad จะได้ช่วยพวกเขากลับคืนบ้าง!"
    }
  }
];

const Team = () => {
  const { ui } = useUiLang();

  return (
    <div className="team-container">
      {teamMembers.map((member, index) => (
        <div className="team-member-card" key={index}>
          <img src={member.image} alt={member.name} className="team-member-image" />
          <div className="team-member-info">
            <div className="team-member-heading">
              <span className="member-name">{member.name}</span>
              <span className="member-title">{member.location[ui]}</span>
            </div>
            <hr className="team-underline" />
            <span className="description">{member.description[ui]}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default Team;
